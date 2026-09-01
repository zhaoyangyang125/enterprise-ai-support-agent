from typing import Literal

from pydantic import BaseModel


class LeaveBalanceResponse(BaseModel):
    """定义年假余额 API 的成功响应格式。 / Defines the successful response schema for the leave-balance API."""

    remaining_days: float
    unit: Literal["day"] = "day"
