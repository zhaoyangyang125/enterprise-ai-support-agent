from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.error_handlers import (
    leave_balance_not_found_handler,
    leave_request_error_handler,
    rag_provider_error_handler,
)
from app.api.leave_balance import router as leave_balance_router
from app.api.leave_requests import router as leave_requests_router
from app.api.documents import router as documents_router
from app.api.image_assets import router as image_assets_router
from app.db.session import create_schema
from app.services.errors import LeaveBalanceNotFoundError, LeaveRequestError
from app.services.rag_provider_errors import RagProviderError, EmbeddingIndexMismatchError


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """在 FastAPI 启动时创建所需的数据库表。 / Creates required database tables when FastAPI starts."""

    create_schema()
    yield


app = FastAPI(title="Enterprise AI Support Agent", lifespan=lifespan)
app.add_exception_handler(
    LeaveBalanceNotFoundError,
    leave_balance_not_found_handler,
)
app.add_exception_handler(LeaveRequestError, leave_request_error_handler)
app.add_exception_handler(RagProviderError, rag_provider_error_handler)
app.add_exception_handler(EmbeddingIndexMismatchError, rag_provider_error_handler)
app.include_router(documents_router)
app.include_router(image_assets_router)
app.include_router(leave_balance_router)
app.include_router(leave_requests_router)
app.include_router(chat_router)

_STATIC_DIRECTORY = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIRECTORY), name="static")


@app.get("/", include_in_schema=False, response_class=FileResponse)
def demo_ui() -> FileResponse:
    """返回本地演示用的企业 AI 工作界面。 / Returns the local Enterprise AI demonstration workspace."""

    return FileResponse(_STATIC_DIRECTORY / "index.html")
