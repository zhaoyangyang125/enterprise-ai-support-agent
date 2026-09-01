from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.context import CurrentUser, get_current_user
from app.dependencies import get_leave_service
from app.schemas.leave_balance import LeaveBalanceResponse
from app.services.leave_service import LeaveService

router = APIRouter(prefix="/api/me", tags=["leave"])


@router.get("/leave-balance", response_model=LeaveBalanceResponse)
def get_my_leave_balance(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveBalanceResponse:
    """处理当前用户查询自己年假余额的请求。 / Handles the current user's own leave-balance request."""

    return service.get_my_leave_balance(current_user)
