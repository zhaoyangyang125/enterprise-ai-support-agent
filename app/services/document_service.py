import hashlib
from pathlib import Path

from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalDocumentStorage
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.repositories.vector_repository import VectorIndex
from app.schemas.document import (
    DocumentIngestionResult,
    DocumentVersionStatus,
    ParsedBlock,
)
from app.schemas.rag import IndexedChunk


class DocumentService:
    """协调文档状态、原文件存储、解析、Chunking 和向量索引。 / Coordinates document state, original storage, parsing, chunking, and vector indexing."""

    def __init__(
        self,
        repository: SqlAlchemyDocumentRepository,
        storage: LocalDocumentStorage,
        parser_registry: DocumentParserRegistry,
        vector_index: VectorIndex,
    ) -> None:
        """接收三种存储和解析流程所需的依赖。 / Receives dependencies for the three stores and parsing workflow."""

        self._repository = repository
        self._storage = storage
        self._parser_registry = parser_registry
        self._vector_index = vector_index


    def ingest(
        self,  # 当前 DocumentService 对象，由 Python 自动传入
        source_path: Path,  # 临时上传文件在本地的路径
        document_id: str,  # 文档编号，例如 DOC-001
        title: str,  # 文档标题，例如“员工休假规定”
        document_version_id: str,  # 文档版本的唯一编号，例如 DOCVER-001
        version_label: str,  # 给用户看的版本名称，例如 v1.0
        source_name: str | None = None,  # 原始文件名；没有传入时使用路径中的文件名
        grant_read_to_user_id: str | None = None,  # 处理成功后授予读取权限的用户编号
    ) -> DocumentIngestionResult:  # 返回文档处理结果
        """将本地 PDF/Excel 原文件转换并索引为可授权检索的 Chunk。 / Converts and indexes a local PDF/Excel original into authorization-ready chunks."""

        self._repository.start_processing(
            document_id,
            title,
            document_version_id,
            version_label,
        )
        try:
            original_name = Path(source_name or source_path.name).name
            stored_path = self._storage.store(
                source_path,
                document_id,
                document_version_id,
                file_name=original_name,
            )
            blocks = self._parser_registry.parse_document(
                stored_path, document_id, document_version_id, original_name,
            )
            if not blocks:
                raise ValueError("The document did not contain indexable content")
            chunks = []
            chunk_id_counts: dict[str, int] = {}
            for block in blocks:
                chunk = self._to_chunk(
                    block,
                    original_name,
                    document_id,
                    document_version_id,
                )
                duplicate_index = chunk_id_counts.get(chunk.chunk_id, 0)
                chunk_id_counts[chunk.chunk_id] = duplicate_index + 1
                chunk = self._with_unique_chunk_id(chunk, duplicate_index)
                chunks.append(chunk)
            self._vector_index.upsert_chunks(chunks)
            if grant_read_to_user_id is not None:
                self._repository.grant_user_read(
                    document_id,
                    grant_read_to_user_id,
                )
            self._repository.mark_status(document_version_id, "active")
        except Exception:
            self._repository.mark_status(document_version_id, "failed")
            raise
        return DocumentIngestionResult(
            document_id=document_id,
            document_version_id=document_version_id,
            status="active",
            chunk_count=len(chunks),
            stored_path=stored_path,
        )

    def list_versions(self, limit: int = 50) -> list[DocumentVersionStatus]:
        """取得文档管理界面需要的版本状态。 / Retrieves document-version states required by the management UI."""

        return [
            DocumentVersionStatus(
                document_id=version.document_id,
                document_version_id=version.document_version_id,
                title=title,
                version_label=version.version_label,
                status=version.status,
            )
            for version, title in self._repository.list_versions(limit)
        ]

    @staticmethod
    def _to_chunk(
        block: ParsedBlock,
        source_name: str,
        document_id: str,
        document_version_id: str,
    ) -> IndexedChunk:
        """使用内容和定位生成稳定 ID，并保留 citation metadata。 / Creates a stable ID from content and location while preserving citation metadata."""

        # 旧文本 Chunk 继续使用原来的组成和顺序，避免升级后 ID 全部变化。
        identity_parts: list[object] = [
            document_version_id,
            block.content_type,
            block.page,
            block.sheet,
            block.cell_range,
            block.rows,
            block.section,
            block.content,
        ]
        # 图片证据才追加图片身份。同一页多张图片因此不会得到相同 ID。
        if block.image_id is not None:
            identity_parts.extend([block.image_id, block.image_index])
        identity = "|".join(str(value) for value in identity_parts)
        chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return IndexedChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            document_version_id=document_version_id,
            content=block.content,
            source_name=source_name,
            content_type=block.content_type,
            modality=block.modality,
            extraction_method=block.extraction_method,
            image_id=block.image_id,
            image_index=block.image_index,
            mime_type=block.mime_type,
            confidence=block.confidence,
            page=block.page,
            section=block.section,
            sheet=block.sheet,
            cell_range=block.cell_range,
            rows=block.rows,
        )

    @staticmethod
    def _with_unique_chunk_id(
        chunk: IndexedChunk,
        duplicate_index: int,
    ) -> IndexedChunk:
        """只为同批次重复Chunk生成稳定后缀ID。 / Creates a stable ID only for later duplicate chunks."""

        if duplicate_index == 0:
            return chunk
        identity = f"{chunk.chunk_id}|duplicate|{duplicate_index}"
        unique_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return chunk.model_copy(update={"chunk_id": unique_id})
