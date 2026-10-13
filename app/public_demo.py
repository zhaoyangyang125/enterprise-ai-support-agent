"""Isolated, read-only public application. Never imports the private API wiring."""
import asyncio
import os
import shutil
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.agent.router import AgentRouter
from app.auth.context import CurrentUser
from app.db.models import User
from app.public_demo_fixtures import PUBLIC_DOCUMENT_CHUNKS
from app.public_demo_data import COLLECTION, verify_bundle, verify_public_database
from app.public_demo_limits import PublicLimits
from app.repositories.document_access_repository import SqlAlchemyDocumentAccessRepository
from app.repositories.hybrid_repository import ChromaKeywordRepository, HybridVectorRepository
from app.repositories.leave_repository import SqlAlchemyLeaveRepository
from app.repositories.vector_repository import ChromaVectorRepository
from app.schemas.chat import ChatResponse
from app.schemas.leave_balance import LeaveBalanceResponse
from app.services.authorization_service import AuthorizationService
from app.services.embedding_service import HashEmbeddingProvider
from app.services.leave_service import LeaveService
from app.services.rag_service import EvidenceOnlyAnswerGenerator, RagService
from app.tools.get_leave_balance_tool import GetLeaveBalanceTool
from app.tools.search_document_tool import SearchDocumentTool

STATIC = Path(__file__).parent / "public_static"
PUBLIC_USER = CurrentUser(user_id="U001", department_id="D-SALES", role_ids=frozenset({"EMPLOYEE"}))


class PublicSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    data_dir: Path
    state_dir: Path
    per_minute: int = Field(default=20, ge=1, le=60)
    daily_requests: int = Field(default=200, ge=1, le=2000)
    concurrency: int = Field(default=2, ge=1, le=4)
    timeout_seconds: float = Field(default=10, gt=0, le=30)
    model_mode: Literal["offline"] = "offline"

    @classmethod
    def from_environment(cls):
        # No private RAG_* variables or cloud credentials are read.
        data_dir = os.environ.get("PUBLIC_DEMO_DATA_DIR")
        state_dir = os.environ.get("PUBLIC_DEMO_STATE_DIR")
        if not data_dir or not state_dir:
            raise ValueError("PUBLIC_DEMO_DATA_DIR and PUBLIC_DEMO_STATE_DIR are required")
        return cls(data_dir=Path(data_dir), state_dir=Path(state_dir),
                   per_minute=os.getenv("PUBLIC_DEMO_PER_MINUTE", "20"),
                   daily_requests=os.getenv("PUBLIC_DEMO_DAILY_REQUESTS", "200"),
                   concurrency=os.getenv("PUBLIC_DEMO_CONCURRENCY", "2"),
                   timeout_seconds=os.getenv("PUBLIC_DEMO_TIMEOUT_SECONDS", "10"),
                   model_mode=os.getenv("PUBLIC_DEMO_MODEL_MODE", "offline"))

    def check_paths(self):
        data = self.data_dir.resolve()
        state = self.state_dir.resolve()
        if data == state or data in state.parents or state in data.parents:
            raise ValueError("Public data and quota state must be separate directories")
        private_vector = Path(os.getenv("RAG_VECTOR_PATH", "chroma_data")).resolve()
        private_storage = Path("document_storage").resolve()
        for private in (private_vector, private_storage):
            for public in (data, state):
                if public == private or private in public.parents or public in private.parents:
                    raise ValueError("Public paths overlap private storage")
        private_database = Path("business.db").resolve()
        for public in (data, state):
            if public == private_database or public in private_database.parents:
                raise ValueError("Public paths overlap private database")
        verify_bundle(data)
        verify_public_database(data / "fictional.sqlite3")


class PublicChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=500)


class PublicRuntime:
    def __init__(self, settings: PublicSettings, stack: ExitStack):
        settings.check_paths()
        self.settings = settings
        self.limits = PublicLimits(settings.state_dir, settings.per_minute,
                                   settings.daily_requests, settings.concurrency)
        stack.callback(self.limits.close)
        database = settings.data_dir.resolve() / "fictional.sqlite3"
        database_uri = database.as_uri() + "?mode=ro&immutable=1"

        def connect_read_only():
            connection = sqlite3.connect(database_uri, uri=True, check_same_thread=False)
            connection.execute("PRAGMA query_only=ON")
            return connection

        self.engine = create_engine("sqlite://", creator=connect_read_only)
        stack.callback(self.engine.dispose)

        @event.listens_for(self.engine, "before_cursor_execute")
        def reject_writes(connection, cursor, statement, parameters, context, executemany):
            # SQLite mode=ro remains the authoritative enforcement, including SQL tricks.
            del connection, cursor, parameters, context, executemany
            if not statement.lstrip().upper().startswith("SELECT"):
                raise RuntimeError("Public business database is read-only")

        temporary = stack.enter_context(tempfile.TemporaryDirectory(prefix="public-demo-index-"))
        runtime_index = Path(temporary) / "chroma"
        shutil.copytree(settings.data_dir / "chroma", runtime_index)
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(path=str(runtime_index),
                                           settings=Settings(anonymized_telemetry=False))
        stack.callback(client.close)
        collections = client.list_collections()
        if len(collections) != 1:
            raise ValueError("Public index must contain only the approved collection")
        collection = client.get_collection(COLLECTION)
        self.vector = ChromaVectorRepository(collection, HashEmbeddingProvider())
        chunks = self.vector.list_all_chunks()
        if chunks != PUBLIC_DOCUMENT_CHUNKS:
            raise ValueError("Only approved fictional text chunks are permitted")
        self.retrieval = HybridVectorRepository(self.vector, ChromaKeywordRepository(self.vector))
        with Session(self.engine) as session:
            users = list(session.scalars(select(User.user_id)))
            if users != ["U001"]:
                raise ValueError("Public data must contain only the fictional U001")
            access = SqlAlchemyDocumentAccessRepository(session)
            authorization = AuthorizationService(access)
            allowed = authorization.get_readable_document_version_ids(PUBLIC_USER)
            if allowed != frozenset({"TRAVEL_POLICY-V1"}):
                raise ValueError("Fictional document is not readable by EMPLOYEE")
            self.balance(session)
        self.executor = ThreadPoolExecutor(max_workers=settings.concurrency)
        # ExitStack waits for work BEFORE closing its database/index resources.
        stack.callback(self.executor.shutdown, wait=True)

    @staticmethod
    def balance(session: Session) -> LeaveBalanceResponse:
        service = LeaveService(SqlAlchemyLeaveRepository(session))
        return service.get_my_leave_balance(PUBLIC_USER)

    def chat(self, message: str) -> ChatResponse:
        with Session(self.engine) as session:
            access = SqlAlchemyDocumentAccessRepository(session)
            authorization = AuthorizationService(access)
            rag = RagService(authorization, self.retrieval, EvidenceOnlyAnswerGenerator())
            leave = LeaveService(SqlAlchemyLeaveRepository(session))
            router = AgentRouter(GetLeaveBalanceTool(leave), SearchDocumentTool(rag))
            return router.route(message, PUBLIC_USER)


def create_public_app(settings: PublicSettings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application):
        active_settings = settings
        if active_settings is None:
            active_settings = PublicSettings.from_environment()
        with ExitStack() as stack:
            application.state.runtime = PublicRuntime(active_settings, stack)
            try:
                yield
            finally:
                application.state.runtime = None

    application = FastAPI(title="Public Demo", lifespan=lifespan,
                          docs_url=None, redoc_url=None, openapi_url=None,
                          redirect_slashes=False)

    @application.middleware("http")
    async def boundary(request: Request, call_next):
        path = request.url.path
        allowed = {"/": "GET", "/api/chat": "POST", "/api/me/leave-balance": "GET",
                   "/static/styles.css": "GET", "/static/public.js": "GET"}
        allowed["/static/public.css"] = "GET"
        method = allowed.get(path)
        if method is None:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if request.method != method:
            return JSONResponse({"detail": "Method Not Allowed"}, status_code=405)
        if getattr(request.app.state, "runtime", None) is None:
            return JSONResponse({"detail": "デモを利用できません。"}, status_code=503)
        if request.method == "POST":
            body = bytearray()
            try:
                async with asyncio.timeout(5):
                    async for chunk in request.stream():
                        body.extend(chunk)
                        if len(body) > 8192:
                            return JSONResponse({"detail": "リクエストが大きすぎます。"}, status_code=413)
            except TimeoutError:
                return JSONResponse({"detail": "リクエストの受信がタイムアウトしました。"}, status_code=408)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @application.exception_handler(Exception)
    async def safe_error(request, exception):
        del request, exception
        return JSONResponse({"detail": "デモを利用できません。時間をおいて再試行してください。"}, status_code=503)

    @application.get("/", response_class=FileResponse)
    def home():
        return FileResponse(STATIC / "index.html")

    @application.get("/static/styles.css", response_class=FileResponse)
    def styles():
        return FileResponse(Path(__file__).parent / "static" / "styles.css")

    @application.get("/static/public.js", response_class=FileResponse)
    def javascript():
        return FileResponse(STATIC / "public.js")

    @application.get("/static/public.css", response_class=FileResponse)
    def public_styles():
        return FileResponse(STATIC / "public.css")

    @application.get("/api/me/leave-balance", response_model=LeaveBalanceResponse)
    def balance(request: Request):
        runtime = request.app.state.runtime
        with Session(runtime.engine) as session:
            return runtime.balance(session)

    @application.post("/api/chat", response_model=ChatResponse)
    async def chat(body: PublicChatRequest, request: Request):
        if not body.message.strip():
            raise HTTPException(422, "質問を入力してください。")
        runtime = request.app.state.runtime
        runtime.limits.admit()
        try:
            future = runtime.executor.submit(runtime.chat, body.message)
        except Exception:
            runtime.limits.slots.release()
            raise
        # A timed-out/cancelled request keeps its slot until the actual work ends.
        future.add_done_callback(lambda completed: runtime.limits.slots.release())
        work = asyncio.wrap_future(future)

        def consume_finished_error(completed):
            if not completed.cancelled():
                completed.exception()

        work.add_done_callback(consume_finished_error)
        try:
            return await asyncio.wait_for(asyncio.shield(work), runtime.settings.timeout_seconds)
        except TimeoutError:
            raise HTTPException(504, "処理時間の上限に達しました。") from None

    return application


app = create_public_app()
