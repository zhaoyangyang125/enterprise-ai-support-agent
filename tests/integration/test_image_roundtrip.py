"""用虚构样本验证上传到图片引用，不访问云服务。 / Offline image roundtrip."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from PIL import Image
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.documents import router as documents_router
from app.api.image_assets import router as images_router
from app.auth.context import CurrentUser
from app.db.models import Base, DocumentPermission
from app.dependencies import get_document_service, get_image_asset_service
from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalDocumentStorage, LocalImageAssetStorage
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.repositories.document_access_repository import SqlAlchemyDocumentAccessRepository
from app.repositories.vector_repository import ChromaVectorRepository
from app.services.authorization_service import AuthorizationService
from app.services.document_service import DocumentService
from app.services.embedding_service import HashEmbeddingProvider
from app.services.image_asset_service import ImageAssetService
from app.services.rag_service import RagService, EvidenceOnlyAnswerGenerator
from app.services.vision_service import FakeVisionProvider, VisionResult, VisionDescription


def test_upload_chroma_citation_image_and_revocation(tmp_path):
    """真实解析/存储/Chroma/授权/API，仅Vision返回值为模拟。 / Tests real local layers."""
    picture = tmp_path / "fictional.png"
    Image.new("RGB", (80, 80), "blue").save(picture)
    workbook = Workbook()
    workbook.active.add_image(ExcelImage(picture), "B3")
    source = tmp_path / "fictional.xlsx"
    workbook.save(source)
    workbook.close()
    query = "虚构导航画面保持显示"
    vision = FakeVisionProvider(VisionResult(success=True, provider_name="fake",
        description=VisionDescription(summary=query, image_type="screenshot")))
    storage = LocalImageAssetStorage(tmp_path / "assets")
    registry = DocumentParserRegistry(image_storage=storage, vision_provider=vision, image_mode="vision")
    index = ChromaVectorRepository.persistent(tmp_path / "chroma", "image_roundtrip", HashEmbeddingProvider())
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(documents_router)
    app.include_router(images_router)

    def document_service():
        with Session(engine) as session:
            yield DocumentService(SqlAlchemyDocumentRepository(session),
                LocalDocumentStorage(tmp_path / "assets"), registry, index)

    def image_service():
        with Session(engine) as session:
            authorization = AuthorizationService(SqlAlchemyDocumentAccessRepository(session))
            yield ImageAssetService(authorization, SqlAlchemyDocumentRepository(session), storage)

    app.dependency_overrides[get_document_service] = document_service
    app.dependency_overrides[get_image_asset_service] = image_service
    headers = {"X-User-Id": "U001", "X-Role-Ids": "ADMIN"}
    with TestClient(app) as client:
        response = client.post("/api/admin/documents", headers=headers,
            data={"document_id": "DEMO", "document_version_id": "DEMO-V1",
                  "title": "虚构示例", "version_label": "v1"},
            files={"file": ("fictional.xlsx", source.read_bytes())})
        assert response.status_code == 201
        assert len(vision.requested_image_paths) == 1
        with Session(engine) as session:
            authorization = AuthorizationService(SqlAlchemyDocumentAccessRepository(session))
            rag = RagService(authorization, index, EvidenceOnlyAnswerGenerator())
            answer = rag.answer(query, CurrentUser(user_id="U001"))
            assert answer.evidence_found
            citation = answer.sources[0]
            assert citation.image_id
            assert citation.cell_range == "B3"
            assert "image_path" not in citation.model_dump()
            image = client.get(citation.image_url, headers=headers)
            assert image.status_code == 200
            assert image.content == picture.read_bytes()
            assert client.get(citation.image_url, headers={"X-User-Id": "U002"}).status_code == 403
            session.execute(delete(DocumentPermission))
            session.commit()
            assert not rag.answer(query, CurrentUser(user_id="U001")).evidence_found
            assert client.get(citation.image_url, headers=headers).status_code == 403
    engine.dispose()
