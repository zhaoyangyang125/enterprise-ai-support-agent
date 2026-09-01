from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.services.errors import (
    ConfirmationRequiredError,
    IdempotencyConflictError,
    InsufficientLeaveBalanceError,
    InvalidLeaveDateRangeError,
    LeaveBalanceNotFoundError,
    LeaveRequestError,
    OverlappingLeaveRequestError,
    PendingLeaveActionAlreadyUsedError,
    PendingLeaveActionExpiredError,
    PendingLeaveActionNotFoundError,
)


async def leave_balance_not_found_handler(
    _request: Request,
    _exc: LeaveBalanceNotFoundError,
) -> JSONResponse:
    """将年假余额不存在的业务异常转换为 HTTP 404。 / Maps the missing leave-balance business error to HTTP 404."""

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Leave balance not found."},
    )


async def leave_request_error_handler(
    _request: Request,
    exc: LeaveRequestError,
) -> JSONResponse:
    """将年假申请业务异常转换为安全的 HTTP 响应。 / Maps leave-request business errors to safe HTTP responses."""

    mappings: list[tuple[type[LeaveRequestError], int, str]] = [
        (
            PendingLeaveActionNotFoundError,
            status.HTTP_404_NOT_FOUND,
            "Pending leave request not found.",
        ),
        (
            InvalidLeaveDateRangeError,
            status.HTTP_400_BAD_REQUEST,
            "The leave date range is invalid.",
        ),
        (
            ConfirmationRequiredError,
            status.HTTP_400_BAD_REQUEST,
            "Explicit confirmation is required.",
        ),
        (
            InsufficientLeaveBalanceError,
            status.HTTP_409_CONFLICT,
            "The current leave balance is insufficient.",
        ),
        (
            OverlappingLeaveRequestError,
            status.HTTP_409_CONFLICT,
            "The requested dates overlap an existing leave request.",
        ),
        (
            PendingLeaveActionExpiredError,
            status.HTTP_409_CONFLICT,
            "The confirmation has expired. Please prepare the request again.",
        ),
        (
            PendingLeaveActionAlreadyUsedError,
            status.HTTP_409_CONFLICT,
            "The confirmation has already been used.",
        ),
        (
            IdempotencyConflictError,
            status.HTTP_409_CONFLICT,
            "The idempotency key was already used for another operation.",
        ),
    ]
    for error_type, status_code, detail in mappings:
        if isinstance(exc, error_type):
            return JSONResponse(status_code=status_code, content={"detail": detail})
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "The leave request could not be processed."},
    )
