import hashlib
from pathlib import Path

from openpyxl import Workbook
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Base, DocumentPermission, DocumentVersion
from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalDocumentStorage
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.schemas.document import ParsedBlock
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
            grant_read_to_user_id="U001",
        )
        version = session.get(DocumentVersion, "TRAVEL_POLICY-V1")
        permissions = session.scalars(select(DocumentPermission)).all()

    assert result.status == "active"
    assert result.chunk_count == 1
    assert result.stored_path.exists()
    assert version is not None and version.status == "active"
    assert vector_index.chunks[0].sheet == "Travel"
    assert vector_index.chunks[0].content_type == "table"
    assert vector_index.chunks[0].cell_range == "A1:B2"
    assert vector_index.chunks[0].rows == "2"
    assert vector_index.chunks[0].source_name == "travel.xlsx"
    assert len(permissions) == 1
    assert permissions[0].subject_type == "user"
    assert permissions[0].subject_id == "U001"


def test_list_versions_returns_ui_status_schema(tmp_path) -> None:
    """验证 Service 将数据库版本转换为界面状态结构。 / Verifies the service converts database versions into UI status schemas."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    source = tmp_path / "travel.xlsx"
    create_excel(source)

    with Session(engine) as session:
        service = make_service(
            session,
            tmp_path / "storage",
            RecordingVectorIndex(),
        )
        service.ingest(
            source,
            "TRAVEL_POLICY",
            "Travel Policy",
            "TRAVEL_POLICY-V1",
            "v1",
        )

        statuses = service.list_versions()

    assert [status.model_dump() for status in statuses] == [
        {
            "document_id": "TRAVEL_POLICY",
            "document_version_id": "TRAVEL_POLICY-V1",
            "title": "Travel Policy",
            "version_label": "v1",
            "status": "active",
        }
    ]


def test_ingestion_preserves_original_name_when_source_is_temporary(tmp_path) -> None:
    """验证临时上传路径不会污染原本文件名和 Citation metadata。 / Verifies a temporary upload path does not replace the original filename in storage or citation metadata."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    temporary_source = tmp_path / "tmp-random-name.xlsx"
    create_excel(temporary_source)
    vector_index = RecordingVectorIndex()

    with Session(engine) as session:
        result = make_service(
            session,
            tmp_path / "storage",
            vector_index,
        ).ingest(
            source_path=temporary_source,
            document_id="HMI-SPEC",
            title="HMI Spec",
            document_version_id="HMI-SPEC-V1",
            version_label="v1",
            source_name="fictional_hmi_test_spec.xlsx",
        )

    assert result.stored_path.name == "fictional_hmi_test_spec.xlsx"
    assert vector_index.chunks[0].source_name == "fictional_hmi_test_spec.xlsx"


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


def test_to_chunk_preserves_existing_text_chunk_id_rule() -> None:
    """验证新增图片 metadata 后，旧文本 Chunk ID 的计算结果保持不变。 / Verifies image metadata does not change the existing text chunk-ID rule."""

    block = ParsedBlock(
        content="国内出張の宿泊費上限",
        content_type="paragraph",
        page=3,
        section="2.1 国内出張",
    )
    old_identity = "|".join(
        str(value)
        for value in (
            "TRAVEL-V1",
            block.content_type,
            block.page,
            block.sheet,
            block.cell_range,
            block.rows,
            block.section,
            block.content,
        )
    )
    expected_id = hashlib.sha256(old_identity.encode("utf-8")).hexdigest()

    chunk = DocumentService._to_chunk(
        block,
        "travel.pdf",
        "TRAVEL",
        "TRAVEL-V1",
    )

    assert chunk.chunk_id == expected_id


def test_to_chunk_passes_image_metadata_without_internal_path() -> None:
    """验证图片 metadata 进入索引模型，但服务器内部路径不会进入索引。 / Verifies image metadata reaches indexing without the server-internal path."""

    block = ParsedBlock(
        content="仪表盘警告灯",
        content_type="note",
        modality="image",
        extraction_method="ocr",
        image_id="IMG-001",
        image_path=Path("private/manual/IMG-001.png"),
        image_index=1,
        mime_type="image/png",
        confidence=0.88,
        page=5,
    )

    chunk = DocumentService._to_chunk(
        block,
        "manual.pdf",
        "MANUAL",
        "MANUAL-V1",
    )

    assert chunk.modality == "image"
    assert chunk.extraction_method == "ocr"
    assert chunk.image_id == "IMG-001"
    assert chunk.image_index == 1
    assert chunk.mime_type == "image/png"
    assert chunk.confidence == 0.88
    assert "image_path" not in chunk.model_dump()
