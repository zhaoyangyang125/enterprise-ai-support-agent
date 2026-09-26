import math
import re
from pathlib import Path
from typing import Any, Protocol

from app.schemas.rag import IndexedChunk, RetrievedChunk, RetrievalFilter
from app.services.embedding_service import EmbeddingProvider
from app.services.rag_provider_errors import EmbeddingIndexMismatchError


class VectorRepository(Protocol):
    """定义权限过滤后的语义检索接口。 / Defines the semantic-retrieval interface with authorization filtering."""

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
        metadata_filter: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """只在允许的文档版本内检索相关片段。 / Searches relevant chunks only within allowed document versions."""

        ...


class VectorIndex(Protocol):
    """定义文档 Ingestion 写入向量索引所需的接口。 / Defines the vector-index interface required by document ingestion."""

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        """新增或替换带有来源 metadata 的 Chunk。 / Adds or replaces chunks with source metadata."""

        ...


class InMemoryVectorRepository:
    """提供无需外部服务的本地确定性检索实现。 / Provides deterministic local retrieval without external services."""

    def __init__(self, chunks: list[IndexedChunk]) -> None:
        """保存本地可检索的文档片段。 / Stores document chunks available for local retrieval."""

        self._chunks = list(chunks)

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
        metadata_filter: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """先按权限版本过滤，再计算字符 n-gram 相似度。 / Filters by authorized versions before calculating character n-gram similarity."""

        candidates = (
            chunk
            for chunk in self._chunks
            if chunk.document_version_id in allowed_document_version_ids
            and self._matches_metadata_filter(chunk, metadata_filter)
        )
        ranked = [
            RetrievedChunk(**chunk.model_dump(), score=self._similarity(query, chunk.content))
            for chunk in candidates
        ]
        ranked.sort(key=lambda chunk: chunk.score, reverse=True)
        return ranked[:limit]

    @staticmethod
    def _matches_metadata_filter(
        chunk: IndexedChunk,
        metadata_filter: RetrievalFilter | None,
    ) -> bool:
        """在权限过滤之后应用只会缩小结果集的 metadata 条件。 / Applies metadata conditions that only narrow the authorized result set."""

        if metadata_filter is None:
            return True
        return all(
            (
                not metadata_filter.document_ids
                or chunk.document_id in metadata_filter.document_ids,
                not metadata_filter.source_names
                or chunk.source_name in metadata_filter.source_names,
                not metadata_filter.content_types
                or chunk.content_type in metadata_filter.content_types,
                not metadata_filter.sheets or chunk.sheet in metadata_filter.sheets,
            )
        )

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        """计算适合本地演示的字符二元组余弦相似度。 / Calculates character-bigram cosine similarity for the local demo."""

        left_terms = InMemoryVectorRepository._bigrams(left)
        right_terms = InMemoryVectorRepository._bigrams(right)
        if not left_terms or not right_terms:
            return 0.0
        overlap = len(left_terms & right_terms)
        return overlap / math.sqrt(len(left_terms) * len(right_terms))

    @staticmethod
    def _bigrams(value: str) -> set[str]:
        """将中日英文本规范化为字符二元组集合。 / Normalizes Chinese, Japanese, and English text into character-bigram sets."""

        normalized = re.sub(r"[^\w\u3040-\u30ff\u3400-\u9fff]", "", value.lower())
        if len(normalized) < 2:
            return {normalized} if normalized else set()
        return {normalized[index : index + 2] for index in range(len(normalized) - 1)}

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        """按 chunk_id 新增或替换本地 Chunk。 / Adds or replaces local chunks by chunk ID."""

        by_id = {chunk.chunk_id: chunk for chunk in self._chunks}
        by_id.update({chunk.chunk_id: chunk for chunk in chunks})
        self._chunks = list(by_id.values())


def matches_retrieval_scope(
    chunk: IndexedChunk,
    allowed_document_version_ids: frozenset[str],
    metadata_filter: RetrievalFilter | None,
) -> bool:
    """防御性检查Chunk同时符合授权范围和metadata条件。 / Checks authorization and metadata scope."""
    if chunk.document_version_id not in allowed_document_version_ids:
        return False
    if metadata_filter is None:
        return True
    if metadata_filter.document_ids and chunk.document_id not in metadata_filter.document_ids:
        return False
    if metadata_filter.source_names and chunk.source_name not in metadata_filter.source_names:
        return False
    if metadata_filter.content_types and chunk.content_type not in metadata_filter.content_types:
        return False
    if metadata_filter.sheets and chunk.sheet not in metadata_filter.sheets:
        return False
    return True


class ChromaVectorRepository:
    """使用本地持久化 Chroma 实现权限过滤的向量索引和检索。 / Uses local persistent Chroma for authorization-filtered vector indexing and retrieval."""

    def __init__(self, collection: Any, embedding_provider: EmbeddingProvider) -> None:
        """接收 Chroma collection 和可替换 Embedding Provider。 / Receives a Chroma collection and a replaceable embedding provider."""

        self._collection = collection
        self._embedding_provider = embedding_provider
        self._check_embedding_identity()

    def _check_embedding_identity(self) -> None:
        """真实模型不得复用旧 Hash 或其他模型的索引。 / Rejects incompatible indexes."""
        identity = getattr(self._embedding_provider, "index_identity", None)
        metadata = self._collection.metadata or {}
        stored_identity = metadata.get("embedding_identity")
        if identity is None:
            if stored_identity is not None:
                raise EmbeddingIndexMismatchError(
                    "Embedding index is incompatible; reindex into a separate collection"
                )
            return
        if stored_identity == identity:
            return
        if self._collection.count() > 0:
            raise EmbeddingIndexMismatchError(
                "Embedding index is incompatible; reindex into a separate collection"
            )
        updated_metadata = dict(metadata)
        updated_metadata["embedding_identity"] = identity
        # Chroma 不允许 modify 请求包含 hnsw:space，即使值没变。
        # Chroma rejects hnsw:space on modify even when unchanged.
        updated_metadata.pop("hnsw:space", None)
        self._collection.modify(metadata=updated_metadata)

    @classmethod
    def persistent(
        cls,
        path: Path | str,
        collection_name: str,
        embedding_provider: EmbeddingProvider,
    ) -> "ChromaVectorRepository":
        """创建自动保存到本地目录的 Chroma Repository。 / Creates a Chroma repository that automatically persists to a local directory."""

        import chromadb

        client = chromadb.PersistentClient(path=str(path))
        metadata = {"hnsw:space": "cosine"}
        identity = getattr(embedding_provider, "index_identity", None)
        if identity is not None:
            metadata["embedding_identity"] = identity
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata=metadata,
        )
        return cls(collection, embedding_provider)

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        """将 Chunk、Embedding 和 citation metadata 一起写入 Chroma。 / Writes chunks, embeddings, and citation metadata to Chroma together."""

        if not chunks:
            return
        self._collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            embeddings=self._embedding_provider.embed(
                [chunk.content for chunk in chunks]
            ),
            metadatas=[self._to_metadata(chunk) for chunk in chunks],
        )

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
        metadata_filter: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """在 Chroma query 的 where 条件中应用允许版本集合。 / Applies the allowed version set in the Chroma query where clause."""

        if not allowed_document_version_ids:
            return []
        result = self._collection.query(
            query_embeddings=self._embedding_provider.embed([query]),
            n_results=limit,
            where=self._build_where(
                allowed_document_version_ids,
                metadata_filter,
            ),
            include=["documents", "metadatas", "distances"],
        )
        ids = result["ids"][0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        chunks: list[RetrievedChunk] = []
        for chunk_id, content, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
            strict=True,
        ):
            if content is None or metadata is None or distance is None:
                continue
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    document_id=str(metadata["document_id"]),
                    document_version_id=str(metadata["document_version_id"]),
                    content=content,
                    score=max(0.0, min(1.0, 1.0 - float(distance))),
                    source_name=str(metadata["source_name"]),
                    content_type=self._optional_str(
                        metadata.get("content_type")
                    )
                    or "paragraph",
                    modality=self._optional_str(metadata.get("modality")) or "text",
                    extraction_method=self._optional_str(
                        metadata.get("extraction_method")
                    ),
                    image_id=self._optional_str(metadata.get("image_id")),
                    image_index=self._optional_int(metadata.get("image_index")),
                    mime_type=self._optional_str(metadata.get("mime_type")),
                    confidence=self._optional_float(metadata.get("confidence")),
                    page=self._optional_int(metadata.get("page")),
                    section=self._optional_str(metadata.get("section")),
                    sheet=self._optional_str(metadata.get("sheet")),
                    cell_range=self._optional_str(metadata.get("cell_range")),
                    rows=self._optional_str(metadata.get("rows")),
                )
            )
        return chunks

    def list_authorized_chunks(
        self,
        allowed_document_version_ids: frozenset[str],
        metadata_filter: RetrievalFilter | None = None,
    ) -> list[IndexedChunk]:
        """读取Keyword检索可见的授权Chunk，不执行向量查询。 / Lists authorized chunks for keyword search."""
        if not allowed_document_version_ids:
            return []
        result = self._collection.get(
            where=self._build_where(allowed_document_version_ids, metadata_filter),
            include=["documents", "metadatas"],
        )
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        chunks: list[IndexedChunk] = []
        for index in range(len(ids)):
            content = documents[index]
            metadata = metadatas[index]
            if content is None or metadata is None:
                continue
            chunk = self._from_stored_values(ids[index], content, metadata)
            if matches_retrieval_scope(chunk, allowed_document_version_ids, metadata_filter):
                chunks.append(chunk)
        return chunks

    def list_all_chunks(self) -> list[IndexedChunk]:
        """读取迁移所需的全部 Chunk，不用于用户检索。 / Lists all chunks for controlled migration."""
        result = self._collection.get(include=["documents", "metadatas"])
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        chunks: list[IndexedChunk] = []
        for index in range(len(ids)):
            content = documents[index]
            metadata = metadatas[index]
            if content is None or metadata is None:
                continue
            chunks.append(self._from_stored_values(ids[index], content, metadata))
        return chunks

    @classmethod
    def _from_stored_values(
        cls, chunk_id: str, content: str, metadata: dict[str, object]
    ) -> IndexedChunk:
        """将Chroma文档和metadata恢复为统一Chunk。 / Restores a stored chunk."""
        return IndexedChunk(
            chunk_id=chunk_id,
            document_id=str(metadata["document_id"]),
            document_version_id=str(metadata["document_version_id"]),
            content=content,
            source_name=str(metadata["source_name"]),
            content_type=cls._optional_str(metadata.get("content_type")) or "paragraph",
            modality=cls._optional_str(metadata.get("modality")) or "text",
            extraction_method=cls._optional_str(metadata.get("extraction_method")),
            image_id=cls._optional_str(metadata.get("image_id")),
            image_index=cls._optional_int(metadata.get("image_index")),
            mime_type=cls._optional_str(metadata.get("mime_type")),
            confidence=cls._optional_float(metadata.get("confidence")),
            page=cls._optional_int(metadata.get("page")),
            section=cls._optional_str(metadata.get("section")),
            sheet=cls._optional_str(metadata.get("sheet")),
            cell_range=cls._optional_str(metadata.get("cell_range")),
            rows=cls._optional_str(metadata.get("rows")),
        )

    @staticmethod
    def _build_where(
        allowed_document_version_ids: frozenset[str],
        metadata_filter: RetrievalFilter | None,
    ) -> dict[str, object]:
        """用 AND 合并强制权限条件与可选 metadata 条件。 / Combines mandatory authorization and optional metadata conditions with AND."""

        conditions: list[dict[str, object]] = [
            {
                "document_version_id": {
                    "$in": sorted(allowed_document_version_ids)
                }
            }
        ]
        if metadata_filter is not None:
            for key, values in (
                ("document_id", metadata_filter.document_ids),
                ("source_name", metadata_filter.source_names),
                ("content_type", metadata_filter.content_types),
                ("sheet", metadata_filter.sheets),
            ):
                if values:
                    conditions.append({key: {"$in": sorted(values)}})
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    @staticmethod
    def _to_metadata(chunk: IndexedChunk) -> dict[str, str | int | float | bool]:
        """移除 None 并生成 Chroma 可存储的 citation metadata。 / Removes None values and creates Chroma-compatible citation metadata."""

        metadata: dict[str, str | int | float | bool] = {
            "document_id": chunk.document_id,
            "document_version_id": chunk.document_version_id,
            "source_name": chunk.source_name,
            "content_type": chunk.content_type,
            "modality": chunk.modality,
        }
        # 这里只允许写入可检索的轻量 metadata，不保存图片二进制、绝对路径或 URL。
        for key in (
            "extraction_method",
            "image_id",
            "image_index",
            "mime_type",
            "confidence",
            "page",
            "section",
            "sheet",
            "cell_range",
            "rows",
        ):
            value = getattr(chunk, key)
            if value is not None:
                metadata[key] = value
        return metadata

    @staticmethod
    def _optional_str(value: object) -> str | None:
        """把可选 metadata 安全转换为字符串。 / Safely converts optional metadata to a string."""

        return None if value is None else str(value)

    @staticmethod
    def _optional_int(value: object) -> int | None:
        """把可选 page metadata 安全转换为整数。 / Safely converts optional page metadata to an integer."""

        return None if value is None else int(value)

    @staticmethod
    def _optional_float(value: object) -> float | None:
        """把可选 confidence metadata 安全转换为小数。 / Safely converts optional confidence metadata to a float."""

        return None if value is None else float(value)
