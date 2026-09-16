"""启动完全隔离的图片验收页面。 / Runs an isolated offline image demo.

从项目根目录执行 python -m scripts.image_acceptance_demo。
仅绑定本机；数据存入新临时目录；不会读取原始业务数据或调用云模型。
"""
from pathlib import Path
from tempfile import mkdtemp

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.chat import router as chat_router
from app.api.documents import router as document_router
from app.api.image_assets import router as image_router
from app.db.models import Base
from app.db.session import get_db_session
from app.dependencies import get_document_service, get_image_asset_service, get_vector_repository
from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalDocumentStorage, LocalImageAssetStorage
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.repositories.document_access_repository import SqlAlchemyDocumentAccessRepository
from app.repositories.vector_repository import ChromaVectorRepository
from app.services.authorization_service import AuthorizationService
from app.services.document_service import DocumentService
from app.services.embedding_service import HashEmbeddingProvider
from app.services.image_asset_service import ImageAssetService
from app.services.vision_service import FakeVisionProvider, VisionResult, VisionDescription


def create_demo(root: Path) -> FastAPI:
    """组装真实本地组件，Vision仅返回虚构说明。 / Builds isolated real local components."""
    engine = create_engine("sqlite:///" + str(root / "business.db"),
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    index = ChromaVectorRepository.persistent(root / "chroma", "demo_images", HashEmbeddingProvider())
    image_storage = LocalImageAssetStorage(root / "storage")
    vision = FakeVisionProvider(VisionResult(success=True, provider_name="fake",
        description=VisionDescription(summary="虚构导航画面保持显示", image_type="screenshot")))
    registry = DocumentParserRegistry(image_storage=image_storage, vision_provider=vision, image_mode="vision")

    def sessions():
        """每次请求使用隔离数据库。 / Supplies an isolated database session."""
        with Session(engine) as session:
            yield session

    def documents():
        """组装隔离上传服务。 / Builds isolated ingestion."""
        with Session(engine) as session:
            yield DocumentService(SqlAlchemyDocumentRepository(session),
                LocalDocumentStorage(root / "storage"), registry, index)

    def images():
        """复用正式权限逻辑读取测试图片。 / Reuses real image authorization."""
        with Session(engine) as session:
            authorization = AuthorizationService(SqlAlchemyDocumentAccessRepository(session))
            yield ImageAssetService(authorization, SqlAlchemyDocumentRepository(session), image_storage)

    picture = root / "fictional.png"
    image = Image.new("RGB", (640, 320), "#123b34")
    draw = ImageDraw.Draw(image)
    draw.text((30, 40), "FICTIONAL NAVIGATION SCREEN", fill="white")
    draw.rectangle((40, 100, 590, 260), outline="#70d7ae", width=4)
    draw.text((70, 160), "TEST ONLY - KEEP NAVIGATION DISPLAY", fill="white")
    image.save(picture)
    workbook = Workbook()
    workbook.active.title = "Demo"
    workbook.active.add_image(ExcelImage(picture), "B3")
    source = root / "fictional.xlsx"
    workbook.save(source)
    workbook.close()
    with Session(engine) as session:
        service = DocumentService(SqlAlchemyDocumentRepository(session),
            LocalDocumentStorage(root / "storage"), registry, index)
        service.ingest(source, "DEMO", "虚构图片验收", "DEMO-V1", "v1", grant_read_to_user_id="U001")

    app = FastAPI(title="Offline image acceptance")
    app.include_router(chat_router)
    app.include_router(document_router)
    app.include_router(image_router)
    app.dependency_overrides[get_db_session] = sessions
    app.dependency_overrides[get_vector_repository] = lambda: index
    app.dependency_overrides[get_document_service] = documents
    app.dependency_overrides[get_image_asset_service] = images
    static = Path(__file__).resolve().parents[1] / "app" / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def home():
        """显示正式页面，数据来自隔离环境。 / Serves the existing UI."""
        return FileResponse(static / "index.html")

    return app


if __name__ == "__main__":
    import uvicorn

    directory = Path(mkdtemp(prefix="project3-image-demo-"))
    print("Isolated data:", directory)
    print("Question: 虚构导航画面保持显示 | User: U001; denied user: U002")
    uvicorn.run(create_demo(directory), host="127.0.0.1", port=8768)
