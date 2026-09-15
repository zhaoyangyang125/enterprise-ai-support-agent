from typing import Annotated
from functools import lru_cache
from pathlib import Path
import os

from fastapi import Depends
from sqlalchemy.orm import Session

from app.agent.router import AgentRouter
from app.db.session import get_db_session
from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalDocumentStorage, LocalImageAssetStorage
from app.services.gemini_vision_provider import GeminiVisionProvider
from app.repositories.document_access_repository import (
    SqlAlchemyDocumentAccessRepository,
)
from app.repositories.leave_repository import SqlAlchemyLeaveRepository
from app.repositories.leave_request_repository import SqlAlchemyLeaveRequestRepository
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.repositories.vector_repository import ChromaVectorRepository
from app.services.authorization_service import AuthorizationService
from app.services.embedding_service import HashEmbeddingProvider
from app.services.document_service import DocumentService
from app.services.leave_service import LeaveService
from app.services.leave_request_service import LeaveRequestService
from app.services.rag_service import EvidenceOnlyAnswerGenerator, RagService
from app.tools.get_leave_balance_tool import GetLeaveBalanceTool
from app.tools.create_leave_request_tool import CreateLeaveRequestTool
from app.tools.search_document_tool import SearchDocumentTool


def get_leave_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> LeaveService:
    """组装并提供使用真实 Repository 的 LeaveService。 / Builds and provides a LeaveService backed by the real repository."""

    repository = SqlAlchemyLeaveRepository(session)
    return LeaveService(repository)


def get_leave_request_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> LeaveRequestService:
    """组装并提供事务性年假申请 Service。 / Builds and provides the transactional leave-request service."""

    repository = SqlAlchemyLeaveRequestRepository(session)
    return LeaveRequestService(repository)


def get_create_leave_request_tool(
    service: Annotated[LeaveRequestService, Depends(get_leave_request_service)],
) -> CreateLeaveRequestTool:
    """为 Agent 组装复用安全写入 Service 的申请 Tool。 / Builds the leave-request tool that reuses the safe write service for the agent."""

    return CreateLeaveRequestTool(service)


@lru_cache
def get_vector_repository() -> ChromaVectorRepository:
    """创建并缓存本地持久化 Chroma Repository。 / Creates and caches the local persistent Chroma repository."""

    return ChromaVectorRepository.persistent(
        path=Path("chroma_data"),
        collection_name="enterprise_documents",
        embedding_provider=HashEmbeddingProvider(),
    )


def get_rag_service(
    session: Annotated[Session, Depends(get_db_session)],
    vector_repository: Annotated[
        ChromaVectorRepository,
        Depends(get_vector_repository),
    ],
) -> RagService:
    """组装本地开发用的 Authorized RAG Service。 / Builds the Authorized RAG service for local development."""

    access_repository = SqlAlchemyDocumentAccessRepository(session)
    authorization_service = AuthorizationService(access_repository)
    answer_generator = EvidenceOnlyAnswerGenerator()
    return RagService(
        authorization_service=authorization_service,
        vector_repository=vector_repository,
        answer_generator=answer_generator,
    )


def get_document_service(
    session: Annotated[Session, Depends(get_db_session)],
    vector_repository: Annotated[
        ChromaVectorRepository,
        Depends(get_vector_repository),
    ],
) -> DocumentService:
    """组装文档上传、解析、存储和索引所需的 Service。 / Builds the service required for document upload, parsing, storage, and indexing."""

    registry = DocumentParserRegistry()
    if os.getenv("DOCUMENT_IMAGE_MODE", "off") == "vision":
        provider = GeminiVisionProvider(
            api_key=os.getenv("GEMINI_API_KEY"),
            model_name=os.getenv("GEMINI_VISION_MODEL"),
        )
        registry = DocumentParserRegistry(
            image_storage=LocalImageAssetStorage(Path("document_storage")),
            vision_provider=provider, image_mode="vision",
        )
    return DocumentService(
        repository=SqlAlchemyDocumentRepository(session),
        storage=LocalDocumentStorage(Path("document_storage")),
        parser_registry=registry,
        vector_index=vector_repository,
    )


def get_agent_router(
    leave_service: Annotated[LeaveService, Depends(get_leave_service)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
) -> AgentRouter:
    """组装两个只读 Tool 和 Agent Router。 / Builds the two read-only tools and the agent router."""

    return AgentRouter(
        leave_balance_tool=GetLeaveBalanceTool(leave_service),
        search_document_tool=SearchDocumentTool(rag_service),
    )
