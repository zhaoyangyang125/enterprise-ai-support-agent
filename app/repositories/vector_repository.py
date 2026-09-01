import math
import re
from pathlib import Path
from typing import Any, Protocol

from app.schemas.rag import IndexedChunk, RetrievedChunk
from app.services.embedding_service import EmbeddingProvider


class VectorRepository(Protocol):
    """定义权限过滤后的语义检索接口。 / Defines the semantic-retrieval interface with authorization filtering."""

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
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
    ) -> list[RetrievedChunk]:
        """先按权限版本过滤，再计算字符 n-gram 相似度。 / Filters by authorized versions before calculating character n-gram similarity."""

        candidates = (
            chunk
            for chunk in self._chunks
            if chunk.document_version_id in allowed_document_version_ids
        )
        ranked = [
            RetrievedChunk(**chunk.model_dump(), score=self._similarity(query, chunk.content))
            for chunk in candidates
        ]
        ranked.sort(key=lambda chunk: chunk.score, reverse=True)
        return ranked[:limit]

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


class ChromaVectorRepository:
    """使用本地持久化 Chroma 实现权限过滤的向量索引和检索。 / Uses local persistent Chroma for authorization-filtered vector indexing and retrieval."""

    def __init__(self, collection: Any, embedding_provider: EmbeddingProvider) -> None:
        """接收 Chroma collection 和可替换 Embedding Provider。 / Receives a Chroma collection and a replaceable embedding provider."""

        self._collection = collection
        self._embedding_provider = embedding_provider

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
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
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
    ) -> list[RetrievedChunk]:
        """在 Chroma query 的 where 条件中应用允许版本集合。 / Applies the allowed version set in the Chroma query where clause."""

        if not allowed_document_version_ids:
            return []
        result = self._collection.query(
            query_embeddings=self._embedding_provider.embed([query]),
            n_results=limit,
            where={
                "document_version_id": {
                    "$in": sorted(allowed_document_version_ids)
                }
            },
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
                    page=self._optional_int(metadata.get("page")),
                    section=self._optional_str(metadata.get("section")),
                    sheet=self._optional_str(metadata.get("sheet")),
                    rows=self._optional_str(metadata.get("rows")),
                )
            )
        return chunks

    @staticmethod
    def _to_metadata(chunk: IndexedChunk) -> dict[str, str | int | float | bool]:
        """移除 None 并生成 Chroma 可存储的 citation metadata。 / Removes None values and creates Chroma-compatible citation metadata."""

        metadata: dict[str, str | int | float | bool] = {
            "document_id": chunk.document_id,
            "document_version_id": chunk.document_version_id,
            "source_name": chunk.source_name,
        }
        for key in ("page", "section", "sheet", "rows"):
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
