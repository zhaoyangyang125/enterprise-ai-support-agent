from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.error_handlers import leave_balance_not_found_handler
from app.api.leave_balance import router as leave_balance_router
from app.db.session import create_schema
from app.services.errors import LeaveBalanceNotFoundError


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
app.include_router(leave_balance_router)
