from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PrepareLeaveRequestRequest(BaseModel):
    """定义年假申请 Prepare 阶段的日期输入。 / Defines date input for the leave-request prepare stage."""

    start_date: date
    end_date: date


class LeaveRequestPreview(BaseModel):
    """定义用户确认前必须看到的完整申请预览。 / Defines the complete request preview shown before user confirmation."""

    confirmation_token: str
    start_date: date
    end_date: date
    requested_days: float
    current_balance: float
    remaining_after_request: float
    approval_required: bool
    expires_at: datetime
    status: Literal["WAITING_CONFIRMATION"] = "WAITING_CONFIRMATION"


class ConfirmLeaveRequestRequest(BaseModel):
    """定义最终创建阶段的明确确认输入。 / Defines explicit confirmation input for the final creation stage."""

    confirmation_token: str = Field(min_length=16, max_length=256)
    confirmed: bool


class LeaveRequestResponse(BaseModel):
    """定义事务提交成功后的年假申请结果。 / Defines the leave-request result after a successful transaction commit."""

    request_id: str
    start_date: date
    end_date: date
    requested_days: float
    remaining_after_request: float
    approval_required: bool
    status: Literal["PENDING_APPROVAL", "SUBMITTED"]
