from app.auth.context import CurrentUser
from app.schemas.chat import ChatResponse
from app.schemas.rag import RetrievalFilter
from app.services.rag_service import RagService


class SearchDocumentTool:
    """将 Agent 的知识查询安全地桥接到 Authorized RAG。 / Safely bridges the agent's knowledge query to Authorized RAG."""

    def __init__(self, service: RagService) -> None:
        """接收执行授权检索的 RAG Service。 / Receives the RAG service that performs authorized retrieval."""

        self._service = service

    def execute(
        self,
        query: str,
        current_user: CurrentUser,
        metadata_filter: RetrievalFilter | None = None,
    ) -> ChatResponse:
        """执行授权文档查询并保持证据状态与引用。 / Executes an authorized document query while preserving evidence state and citations."""

        result = self._service.answer(query, current_user, metadata_filter)
        return ChatResponse(
            intent="knowledge_query",
            answer=result.answer,
            evidence_found=result.evidence_found,
            sources=result.sources,
        )
