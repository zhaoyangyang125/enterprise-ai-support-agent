"""验证真实Excel到数据库状态和索引的图片链。 / Tests mixed image ingestion."""
from pathlib import Path

import pytest
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, DocumentVersion
from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalDocumentStorage, LocalImageAssetStorage
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.services.document_service import DocumentService
from app.services.vision_service import VisionResult, VisionDescription
from app.services.ocr_service import FakeOcrProvider, OcrResult


class RecordingIndex:
    """记录要索引的内容。 / Records chunks."""
    def __init__(self):
        self.chunks = []

    def upsert_chunks(self, chunks):
        self.chunks.extend(chunks)


class PartialVision:
    """第一张抛异常，第二张成功。 / Fails once then succeeds."""
    def __init__(self):
        self.calls = 0

    def analyze(self, path, context):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("PRIVATE_ERROR")
        return VisionResult(success=True, provider_name="fake",
            description=VisionDescription(summary="虚构导航画面", image_type="screenshot"))


@pytest.mark.parametrize("mode", ["off", "vision", "ocr"])
def test_mixed_excel_ingestion(tmp_path, mode):
    """一张失败不影响其他内容，默认关闭不处理图片。 / Isolates failures and respects off mode."""
    image_path = tmp_path / "fictional.png"
    Image.new("RGB", (80, 80), "blue").save(image_path)
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "虚构说明"
    sheet.add_image(ExcelImage(image_path), "B3")
    sheet.add_image(ExcelImage(image_path), "B8")
    source = tmp_path / "source.xlsx"
    workbook.save(source)
    workbook.close()
    vision = PartialVision()
    ocr = FakeOcrProvider(OcrResult("虚构OCR", None, "fake", True))
    registry = DocumentParserRegistry(
        image_storage=LocalImageAssetStorage(tmp_path / "storage"),
        vision_provider=vision, ocr_provider=ocr, image_mode=mode,
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    index = RecordingIndex()
    with Session(engine) as session:
        service = DocumentService(SqlAlchemyDocumentRepository(session),
            LocalDocumentStorage(tmp_path / "storage"), registry, index)
        result = service.ingest(source, "DOC", "Demo", "VER", "v1")
        assert result.status == "active"
        assert session.get(DocumentVersion, "VER").status == "active"
    image_chunks = []
    for chunk in index.chunks:
        assert "PRIVATE_ERROR" not in chunk.content
        if chunk.image_id:
            image_chunks.append(chunk)
            assert chunk.cell_range in ("B3", "B8")
            assert not hasattr(chunk, "image_path")
    expected = {"off": 0, "vision": 1, "ocr": 2}
    assert len(image_chunks) == expected[mode]
    engine.dispose()
