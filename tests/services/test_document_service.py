from pathlib import Path

from openpyxl import Workbook
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, DocumentVersion
from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalDocumentStorage
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.schemas.rag import IndexedChunk
from app.services.document_service import DocumentService


class RecordingVectorIndex:
    """记录 DocumentService 写入的 Chunk。 / Records chunks written by the document service."""

    def __init__(self, should_fail: bool = False) -> None:
        """设置是否模拟向量索引故障。 / Configures whether to simulate a vector-index failure."""

        self.should_fail = should_fail
        self.chunks: list[IndexedChunk] = []

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        """记录 Chunk 或抛出模拟故障。 / Records chunks or raises a simulated failure."""

        if self.should_fail:
            raise RuntimeError("simulated vector failure")
        self.chunks.extend(chunks)


def create_excel(path: Path) -> None:
    """创建用于 Ingestion 测试的最小语义 Excel。 / Creates a minimal semantic Excel file for ingestion tests."""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Travel"
    sheet.append(["Rule", "Value"])
    sheet.append(["Hotel limit", 10000])
    workbook.save(path)
    workbook.close()


def make_service(
    session: Session,
    storage_root: Path,
    vector_index: RecordingVectorIndex,
) -> DocumentService:
    """组装使用真实 Business DB、Storage 和 Parser 的 DocumentService。 / Builds DocumentService with a real business DB, storage, and parser."""

    return DocumentService(
        repository=SqlAlchemyDocumentRepository(session),
        storage=LocalDocumentStorage(storage_root),
        parser_registry=DocumentParserRegistry(),
        vector_index=vector_index,
    )


def test_ingestion_stores_original_indexes_metadata_and_activates_version(
    tmp_path,
) -> None:
    """验证成功 Ingestion 同时完成原本存储、metadata 索引和 active 状态。 / Verifies successful ingestion stores the original, indexes metadata, and activates the version."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    source = tmp_path / "travel.xlsx"
    create_excel(source)
    vector_index = RecordingVectorIndex()

    with Session(engine) as session:
        result = make_service(session, tmp_path / "storage", vector_index).ingest(
            source_path=source,
            document_id="TRAVEL_POLICY",
            title="Travel Policy",
            document_version_id="TRAVEL_POLICY-V1",
            version_label="v1",
        )
        version = session.get(DocumentVersion, "TRAVEL_POLICY-V1")

    assert result.status == "active"
    assert result.chunk_count == 1
    assert result.stored_path.exists()
    assert version is not None and version.status == "active"
    assert vector_index.chunks[0].sheet == "Travel"
    assert vector_index.chunks[0].rows == "2"
    assert vector_index.chunks[0].source_name == "travel.xlsx"


def test_ingestion_marks_version_failed_when_vector_index_fails(tmp_path) -> None:
    """验证跨存储流程失败时 Business DB 显示 failed 而不是 active。 / Verifies a cross-store failure leaves the business database at failed, not active."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    source = tmp_path / "travel.xlsx"
    create_excel(source)

    with Session(engine) as session:
        service = make_service(
            session,
            tmp_path / "storage",
            RecordingVectorIndex(should_fail=True),
        )
        with pytest.raises(RuntimeError, match="simulated vector failure"):
            service.ingest(
                source,
                "TRAVEL_POLICY",
                "Travel Policy",
                "TRAVEL_POLICY-V1",
                "v1",
            )
        version = session.get(DocumentVersion, "TRAVEL_POLICY-V1")

    assert version is not None and version.status == "failed"
