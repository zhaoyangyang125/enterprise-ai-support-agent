from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from app.auth.context import CurrentUser, get_current_user
from app.dependencies import get_leave_request_service
from app.schemas.leave_request import (
    ConfirmLeaveRequestRequest,
    LeaveRequestPreview,
    LeaveRequestResponse,
    PrepareLeaveRequestRequest,
)
from app.services.leave_request_service import LeaveRequestService


router = APIRouter(prefix="/api/me/leave-requests", tags=["leave"])


@router.post("/prepare", response_model=LeaveRequestPreview)
def prepare_leave_request(
    request: PrepareLeaveRequestRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[LeaveRequestService, Depends(get_leave_request_service)],
) -> LeaveRequestPreview:
    """生成提交前必须由当前用户确认的申请预览。 / Creates the request preview that the current user must confirm before submission."""

    return service.prepare(
        current_user=current_user,
        start_date=request.start_date,
        end_date=request.end_date,
    )


@router.post("", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
def create_leave_request(
    request: ConfirmLeaveRequestRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[LeaveRequestService, Depends(get_leave_request_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> LeaveRequestResponse:
    """明确确认后以幂等方式创建当前用户的年假申请。 / Idempotently creates the current user's leave request after explicit confirmation."""

    return service.confirm(
        current_user=current_user,
        confirmation_token=request.confirmation_token,
        confirmed=request.confirmed,
        idempotency_key=idempotency_key,
    )
