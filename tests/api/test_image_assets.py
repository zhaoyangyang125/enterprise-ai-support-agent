"""图片API使用真实授权查询和隔离文件。 / Tests image API with real authorization."""
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.image_assets import router
from app.db.models import Base, DocumentVersion, DocumentPermission
from app.schemas.rag import RetrievedChunk
from app.services.rag_service import RagService
from app.dependencies import get_image_asset_service
from app.document_processing.storage import LocalImageAssetStorage
from app.repositories.document_access_repository import SqlAlchemyDocumentAccessRepository
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.services.authorization_service import AuthorizationService
from app.services.image_asset_service import ImageAssetService


@pytest.fixture
def image_api(tmp_path):
    """创建仅供本测试使用的数据库与图片目录。 / Creates isolated resources."""
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    storage = LocalImageAssetStorage(tmp_path)
    content = b"fictional image bytes"
    asset = storage.store(content, "DOC", "VER", 1, "image/png")
    with Session(engine) as session:
        repository = SqlAlchemyDocumentRepository(session)
        repository.start_processing("DOC", "Demo", "VER", "v1")
        repository.grant_user_read("DOC", "U001")
        repository.mark_status("VER", "active")
    app = FastAPI()
    app.include_router(router)

    def service_dependency():
        with Session(engine) as session:
            authorization = AuthorizationService(SqlAlchemyDocumentAccessRepository(session))
            yield ImageAssetService(authorization, SqlAlchemyDocumentRepository(session), storage)

    app.dependency_overrides[get_image_asset_service] = service_dependency
    with TestClient(app) as client:
        yield client, engine, asset, content
    engine.dispose()


def test_authorized_image_response(image_api):
    client, engine, asset, content = image_api
    url = f"/api/documents/DOC/versions/VER/assets/{asset.image_id}"
    response = client.get(url, headers={"X-User-Id": "U001"})
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"


def test_citation_link_rechecks_revoked_permission(image_api):
    """旧链接在权限撤销后也必须拒绝。 / Existing links cannot bypass revoked access."""
    client, engine, asset, content = image_api
    chunk = RetrievedChunk(chunk_id="CHUNK", document_id="DOC",
        document_version_id="VER", content="虚构图片", score=0.9,
        source_name="fictional.xlsx", modality="image", image_id=asset.image_id)
    citations = RagService._build_citations([chunk])
    url = citations[0].image_url
    assert client.get(url, headers={"X-User-Id": "U001"}).content == content
    with Session(engine) as session:
        session.execute(delete(DocumentPermission))
        session.commit()
    response = client.get(url, headers={"X-User-Id": "U001"})
    assert response.status_code == 403


@pytest.mark.parametrize("case,expected", [
    ("denied", 403), ("inactive", 403), ("expired", 403),
    ("wrong_document", 404), ("missing", 404), ("invalid", 422), ("no_identity", 422),
])
def test_image_access_boundaries(image_api, case, expected):
    client, engine, asset, content = image_api
    document = "DOC"
    image_id = asset.image_id
    headers = {"X-User-Id": "U001"}
    if case == "denied":
        headers = {"X-User-Id": "U002"}
    if case == "no_identity":
        headers = {}
    if case in ("inactive", "expired"):
        with Session(engine) as session:
            version = session.get(DocumentVersion, "VER")
            if case == "inactive":
                version.status = "inactive"
            else:
                version.effective_to = datetime(2000, 1, 1)
            session.commit()
    if case == "wrong_document":
        document = "OTHER"
    if case == "missing":
        image_id = "img_" + "0" * 64
    if case == "invalid":
        image_id = "not-an-image-id"
    response = client.get(f"/api/documents/{document}/versions/VER/assets/{image_id}", headers=headers)
    assert response.status_code == expected
    assert response.content != content
    assert str(asset.path).encode() not in response.content
