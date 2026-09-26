from typing import Annotated
from functools import lru_cache
from pathlib import Path
import os
import logging

from fastapi import Depends
from sqlalchemy.orm import Session

from app.agent.router import AgentRouter
from app.db.session import get_db_session
from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalDocumentStorage, LocalImageAssetStorage
from app.services.gemini_vision_provider import GeminiVisionProvider
from app.services.google_cloud_vision_ocr_provider import GoogleCloudVisionOcrProvider
from app.services.image_asset_service import ImageAssetService
from app.repositories.document_access_repository import (
    SqlAlchemyDocumentAccessRepository,
)
from app.repositories.leave_repository import SqlAlchemyLeaveRepository
from app.repositories.leave_request_repository import SqlAlchemyLeaveRequestRepository
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.repositories.vector_repository import ChromaVectorRepository
from app.repositories.hybrid_repository import (
    ChromaKeywordRepository,
    HybridVectorRepository,
)
from app.services.authorization_service import AuthorizationService
from app.services.embedding_service import EmbeddingProvider, HashEmbeddingProvider
from app.services.gemini_rag_providers import GeminiAnswerGenerator, GeminiEmbeddingProvider
from app.services.dashscope_rag_providers import (
    DashScopeEmbeddingProvider,
    QwenAnswerGenerator,
)
from app.services.document_service import DocumentService
from app.services.leave_service import LeaveService
from app.services.leave_request_service import LeaveRequestService
from app.services.rag_service import AnswerGenerator, EvidenceOnlyAnswerGenerator, RagService
from app.tools.get_leave_balance_tool import GetLeaveBalanceTool
from app.tools.create_leave_request_tool import CreateLeaveRequestTool
from app.tools.search_document_tool import SearchDocumentTool


def get_leave_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> LeaveService:
    """组装并提供使用真实 Repository 的 LeaveService。 / Builds and provides a LeaveService backed by the real repository."""

    repository = SqlAlchemyLeaveRepository(session)
    return LeaveService(repository)


def get_image_asset_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ImageAssetService:
    """组装复用当前数据库授权的图片服务。 / Builds authorized image service."""
    access = SqlAlchemyDocumentAccessRepository(session)
    authorization = AuthorizationService(access)
    repository = SqlAlchemyDocumentRepository(session)
    storage = LocalImageAssetStorage(Path("document_storage"))
    return ImageAssetService(authorization, repository, storage)


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
        path=Path(os.getenv("RAG_VECTOR_PATH", "chroma_data")),
        collection_name=os.getenv(
            "RAG_VECTOR_COLLECTION",
            "enterprise_documents",
        ),
        embedding_provider=build_embedding_provider(),
    )


def build_embedding_provider() -> EmbeddingProvider:
    """显式选择本地或真实 Embedding；配置错误立即失败。 / Selects embedding explicitly."""
    mode = os.getenv("RAG_EMBEDDING_MODE", "hash").strip().lower()
    if mode == "hash":
        return HashEmbeddingProvider()
    dimensions = int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "1024"))
    timeout = float(os.getenv("RAG_PROVIDER_TIMEOUT_SECONDS", "30"))
    if mode == "gemini":
        return GeminiEmbeddingProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model_name=os.getenv("RAG_EMBEDDING_MODEL", ""),
            dimensions=dimensions,
            base_url=os.getenv(
                "RAG_PROVIDER_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta",
            ),
            timeout_seconds=timeout,
        )
    if mode == "dashscope":
        return DashScopeEmbeddingProvider(
            api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            model_name=os.getenv("RAG_EMBEDDING_MODEL", ""),
            dimensions=dimensions,
            base_url=os.getenv(
                "RAG_PROVIDER_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            timeout_seconds=timeout,
        )
    raise ValueError("RAG_EMBEDDING_MODE must be hash, gemini, or dashscope")


def build_answer_generator() -> AnswerGenerator:
    """显式选择本地证据回答或真实 LLM；绝不静默降级。 / Selects answer mode."""
    mode = os.getenv("RAG_ANSWER_MODE", "evidence").strip().lower()
    if mode == "evidence":
        return EvidenceOnlyAnswerGenerator()
    timeout = float(os.getenv("RAG_PROVIDER_TIMEOUT_SECONDS", "30"))
    if mode == "gemini":
        return GeminiAnswerGenerator(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model_name=os.getenv("RAG_ANSWER_MODEL", ""),
            base_url=os.getenv(
                "RAG_PROVIDER_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta",
            ),
            timeout_seconds=timeout,
        )
    if mode == "qwen":
        return QwenAnswerGenerator(
            api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            model_name=os.getenv("RAG_ANSWER_MODEL", ""),
            base_url=os.getenv(
                "RAG_PROVIDER_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            timeout_seconds=timeout,
        )
    raise ValueError("RAG_ANSWER_MODE must be evidence, gemini, or qwen")


def get_rag_minimum_score() -> float:
    """读取 Evidence Gate 的语义分数阈值。 / Reads the semantic evidence threshold."""
    minimum_score = float(os.getenv("RAG_MINIMUM_SCORE", "0.25"))
    if not 0.0 <= minimum_score <= 1.0:
        raise ValueError("RAG_MINIMUM_SCORE must be between 0 and 1")
    return minimum_score


def get_retrieval_repository(
    vector_repository: Annotated[ChromaVectorRepository, Depends(get_vector_repository)],
) -> HybridVectorRepository:
    """组装Vector、BM25和RRF检索，不改变文档写入接口。 / Builds hybrid retrieval."""
    keyword_repository = ChromaKeywordRepository(vector_repository)
    return HybridVectorRepository(vector_repository, keyword_repository)


def get_rag_service(
    session: Annotated[Session, Depends(get_db_session)],
    vector_repository: Annotated[
        HybridVectorRepository,
        Depends(get_retrieval_repository),
    ],
) -> RagService:
    """组装本地开发用的 Authorized RAG Service。 / Builds the Authorized RAG service for local development."""

    access_repository = SqlAlchemyDocumentAccessRepository(session)
    authorization_service = AuthorizationService(access_repository)
    answer_generator = build_answer_generator()
    return RagService(
        authorization_service=authorization_service,
        vector_repository=vector_repository,
        answer_generator=answer_generator,
        minimum_score=get_rag_minimum_score(),
    )


def build_document_parser_registry() -> DocumentParserRegistry:
    """按开关组装真实Provider；无效模式警告并关闭。 / Builds explicitly enabled providers."""
    image_mode = os.getenv("DOCUMENT_IMAGE_MODE", "off").strip().lower()
    ocr_mode = os.getenv("DOCUMENT_OCR_MODE", "off").strip().lower()
    if image_mode not in ("off", "vision", "ocr"):
        logging.getLogger(__name__).warning("invalid_document_image_mode: disabled")
        image_mode = "off"
    if ocr_mode not in ("off", "google"):
        logging.getLogger(__name__).warning("invalid_document_ocr_mode: disabled")
        ocr_mode = "off"
    ocr = None
    vision = None
    if ocr_mode == "google":
        ocr = GoogleCloudVisionOcrProvider()
    if image_mode == "ocr" and ocr is None:
        logging.getLogger(__name__).warning("image_ocr_requires_google_mode: disabled")
        image_mode = "off"
    if image_mode == "vision":
        vision = GeminiVisionProvider(api_key=os.getenv("GEMINI_API_KEY"))
    return DocumentParserRegistry(
        image_storage=LocalImageAssetStorage(Path("document_storage")),
        vision_provider=vision, ocr_provider=ocr, image_mode=image_mode)


def get_document_service(
    session: Annotated[Session, Depends(get_db_session)],
    vector_repository: Annotated[
        ChromaVectorRepository,
        Depends(get_vector_repository),
    ],
) -> DocumentService:
    """组装文档上传、解析、存储和索引所需的 Service。 / Builds the service required for document upload, parsing, storage, and indexing."""

    registry = build_document_parser_registry()
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
