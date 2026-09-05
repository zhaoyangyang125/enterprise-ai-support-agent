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
        self,
        source_path: Path,
        document_id: str,
        title: str,
        document_version_id: str,
        version_label: str,
        source_name: str | None = None,
        grant_read_to_user_id: str | None = None,
    ) -> DocumentIngestionResult:
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
            parser = self._parser_registry.get(stored_path)
            blocks = parser.parse(stored_path)
            if not blocks:
                raise ValueError("The document did not contain indexable content")
            chunks = [
                self._to_chunk(
                    block,
                    original_name,
                    document_id,
                    document_version_id,
                )
                for block in blocks
            ]
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

        identity = "|".join(
            str(value)
            for value in (
                document_version_id,
                block.content_type,
                block.page,
                block.sheet,
                block.cell_range,
                block.rows,
                block.section,
                block.content,
            )
        )
        chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return IndexedChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            document_version_id=document_version_id,
            content=block.content,
            source_name=source_name,
            content_type=block.content_type,
            page=block.page,
            section=block.section,
            sheet=block.sheet,
            cell_range=block.cell_range,
            rows=block.rows,
        )
