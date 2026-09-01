import hashlib
from pathlib import Path

from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalDocumentStorage
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.repositories.vector_repository import VectorIndex
from app.schemas.document import DocumentIngestionResult, ParsedBlock
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
    ) -> DocumentIngestionResult:
        """将本地 PDF/Excel 原文件转换并索引为可授权检索的 Chunk。 / Converts and indexes a local PDF/Excel original into authorization-ready chunks."""

        self._repository.start_processing(
            document_id,
            title,
            document_version_id,
            version_label,
        )
        try:
            stored_path = self._storage.store(
                source_path,
                document_id,
                document_version_id,
            )
            parser = self._parser_registry.get(stored_path)
            blocks = parser.parse(stored_path)
            if not blocks:
                raise ValueError("The document did not contain indexable content")
            chunks = [
                self._to_chunk(
                    block,
                    source_path.name,
                    document_id,
                    document_version_id,
                )
                for block in blocks
            ]
            self._vector_index.upsert_chunks(chunks)
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
                block.page,
                block.sheet,
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
            page=block.page,
            section=block.section,
            sheet=block.sheet,
            rows=block.rows,
        )
