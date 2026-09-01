from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.leave_balance import LeaveBalanceResponse
from app.schemas.rag import SourceCitation


class ChatRequest(BaseModel):
    """定义 AI Chat API 接收的自然语言请求。 / Defines the natural-language request accepted by the AI Chat API."""

    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    """定义 Agent 完成一次只读任务后的统一响应。 / Defines the unified response after the agent completes one read-only task."""

    intent: Literal["leave_balance", "knowledge_query"]
    answer: str
    evidence_found: bool | None = None
    sources: list[SourceCitation] = Field(default_factory=list)
    leave_balance: LeaveBalanceResponse | None = None
