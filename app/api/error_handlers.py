from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.services.errors import LeaveBalanceNotFoundError


async def leave_balance_not_found_handler(
    _request: Request,
    _exc: LeaveBalanceNotFoundError,
) -> JSONResponse:
    """将年假余额不存在的业务异常转换为 HTTP 404。 / Maps the missing leave-balance business error to HTTP 404."""

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Leave balance not found."},
    )
