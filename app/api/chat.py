from typing import Annotated

from fastapi import APIRouter, Depends

from app.agent.router import AgentRouter
from app.auth.context import CurrentUser, get_current_user
from app.dependencies import get_agent_router
from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    agent_router: Annotated[AgentRouter, Depends(get_agent_router)],
) -> ChatResponse:
    """把认证用户的自然语言请求交给 Agent Router。 / Passes the authenticated user's natural-language request to the agent router."""

    return agent_router.route(request.message, current_user)
