from typing import Protocol

from app.auth.context import CurrentUser
from app.repositories.vector_repository import VectorRepository
from app.schemas.rag import RagAnswerResponse, RetrievedChunk, SourceCitation
from app.services.authorization_service import AuthorizationService


NO_EVIDENCE_MESSAGE = "未找到足够的有效资料，无法确认该公司规则。"


class AnswerGenerator(Protocol):
    """定义只根据已授权证据生成回答的接口。 / Defines the interface for generating an answer only from authorized evidence."""

    def generate(self, query: str, evidence: list[RetrievedChunk]) -> str:
        """根据查询和已授权证据生成回答。 / Generates an answer from the query and authorized evidence."""

        ...


class EvidenceOnlyAnswerGenerator:
    """提供不调用外部 LLM 的安全本地回答生成器。 / Provides a safe local answer generator without calling an external LLM."""

    def generate(self, query: str, evidence: list[RetrievedChunk]) -> str:
        """直接返回最高相关证据，供本地端到端开发使用。 / Returns the highest-ranked evidence for local end-to-end development."""

        del query
        return evidence[0].content


class RagService:
    """协调检索前授权、证据判断、回答生成和来源引用。 / Coordinates pre-retrieval authorization, evidence checks, answer generation, and citations."""

    def __init__(
        self,
        authorization_service: AuthorizationService,
        vector_repository: VectorRepository,
        answer_generator: AnswerGenerator,
        minimum_score: float = 0.15,
        retrieval_limit: int = 5,
    ) -> None:
        """接收 RAG 流程依赖项和证据阈值。 / Receives RAG dependencies and the evidence threshold."""

        self._authorization_service = authorization_service
        self._vector_repository = vector_repository
        self._answer_generator = answer_generator
        self._minimum_score = minimum_score
        self._retrieval_limit = retrieval_limit

    def answer(self, query: str, current_user: CurrentUser) -> RagAnswerResponse:
        """只使用当前用户有权读取且证据充分的片段回答。 / Answers only with sufficiently relevant chunks readable by the current user."""

        allowed_version_ids = (
            self._authorization_service.get_readable_document_version_ids(current_user)
        )
        if not allowed_version_ids:
            return self._no_evidence()

        retrieved = self._vector_repository.search(
            query=query,
            allowed_document_version_ids=allowed_version_ids,
            limit=self._retrieval_limit,
        )
        evidence = [chunk for chunk in retrieved if chunk.score >= self._minimum_score]
        if not evidence:
            return self._no_evidence()

        return RagAnswerResponse(
            answer=self._answer_generator.generate(query, evidence),
            evidence_found=True,
            sources=self._build_citations(evidence),
        )

    @staticmethod
    def _no_evidence() -> RagAnswerResponse:
        """创建不调用模型的安全无证据结果。 / Creates a safe no-evidence result without invoking a model."""

        return RagAnswerResponse(
            answer=NO_EVIDENCE_MESSAGE,
            evidence_found=False,
            sources=[],
        )

    @staticmethod
    def _build_citations(evidence: list[RetrievedChunk]) -> list[SourceCitation]:
        """仅从 Chunk metadata 创建去重后的来源引用。 / Builds deduplicated citations only from chunk metadata."""

        citations: list[SourceCitation] = []
        seen: set[tuple[object, ...]] = set()
        for chunk in evidence:
            citation = SourceCitation(
                document_id=chunk.document_id,
                document_version_id=chunk.document_version_id,
                source_name=chunk.source_name,
                page=chunk.page,
                section=chunk.section,
                sheet=chunk.sheet,
                rows=chunk.rows,
            )
            key = tuple(citation.model_dump().values())
            if key not in seen:
                seen.add(key)
                citations.append(citation)
        return citations
