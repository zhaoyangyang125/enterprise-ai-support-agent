from app.auth.context import CurrentUser
from app.schemas.rag import RagAnswerResponse, RetrievedChunk
from app.services.rag_service import NO_EVIDENCE_MESSAGE, RagService


class FakeAuthorizationService:
    """为 RAG 测试返回可控的文档版本权限。 / Returns controllable document-version access for RAG tests."""

    def __init__(self, allowed_version_ids: frozenset[str]) -> None:
        """保存预设权限范围并初始化调用记录。 / Stores the preset access scope and initializes call tracking."""

        self._allowed_version_ids = allowed_version_ids
        self.received_user: CurrentUser | None = None

    def get_readable_document_version_ids(
        self,
        current_user: CurrentUser,
    ) -> frozenset[str]:
        """记录当前用户并返回预设权限范围。 / Records the current user and returns the preset access scope."""

        self.received_user = current_user
        return self._allowed_version_ids


class FakeVectorRepository:
    """为 RAG 测试返回可控证据并记录检索过滤条件。 / Returns controllable evidence and records retrieval filters for RAG tests."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        """保存预设检索结果并初始化调用记录。 / Stores preset retrieval results and initializes call tracking."""

        self._chunks = chunks
        self.calls: list[tuple[str, frozenset[str], int]] = []

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
    ) -> list[RetrievedChunk]:
        """记录检索条件并返回预设证据。 / Records retrieval parameters and returns preset evidence."""

        self.calls.append((query, allowed_document_version_ids, limit))
        return self._chunks


class FakeAnswerGenerator:
    """为 RAG 测试生成固定回答并记录收到的证据。 / Generates a fixed answer and records evidence for RAG tests."""

    def __init__(self) -> None:
        """初始化回答生成调用记录。 / Initializes answer-generation call tracking."""

        self.calls: list[tuple[str, list[RetrievedChunk]]] = []

    def generate(self, query: str, evidence: list[RetrievedChunk]) -> str:
        """记录查询和证据并返回固定回答。 / Records the query and evidence and returns a fixed answer."""

        self.calls.append((query, evidence))
        return "国内出差住宿费上限为每晚 10,000 日元。"


def make_chunk(score: float = 0.9) -> RetrievedChunk:
    """创建带有可信 metadata 的测试证据。 / Creates test evidence with trusted metadata."""

    return RetrievedChunk(
        chunk_id="CHUNK-001",
        document_id="TRAVEL_POLICY",
        document_version_id="TRAVEL_POLICY-V2",
        content="国内出張の宿泊費上限は1泊10,000円です。",
        score=score,
        source_name="TravelPolicy_v2.pdf",
        page=3,
        section="2.1 国内出張",
    )


def test_answer_uses_authorized_versions_and_metadata_citation() -> None:
    """验证 RAG 只按允许版本检索并从 metadata 返回引用。 / Verifies RAG searches only allowed versions and returns metadata citations."""

    authorization = FakeAuthorizationService(frozenset({"TRAVEL_POLICY-V2"}))
    vector_repository = FakeVectorRepository([make_chunk()])
    answer_generator = FakeAnswerGenerator()
    service = RagService(
        authorization_service=authorization,
        vector_repository=vector_repository,
        answer_generator=answer_generator,
        minimum_score=0.5,
    )
    user = CurrentUser(user_id="U001", department_id="D-SALES")

    result = service.answer("国内出差住宿费上限是多少？", user)

    assert result.evidence_found is True
    assert result.answer == "国内出差住宿费上限为每晚 10,000 日元。"
    assert result.sources[0].model_dump() == {
        "document_id": "TRAVEL_POLICY",
        "document_version_id": "TRAVEL_POLICY-V2",
        "source_name": "TravelPolicy_v2.pdf",
        "content_type": "paragraph",
        "page": 3,
        "section": "2.1 国内出張",
        "sheet": None,
        "cell_range": None,
        "rows": None,
    }
    assert vector_repository.calls == [
        ("国内出差住宿费上限是多少？", frozenset({"TRAVEL_POLICY-V2"}), 5)
    ]
    assert len(answer_generator.calls) == 1


def test_answer_returns_no_evidence_without_readable_versions() -> None:
    """验证没有权限范围时不进行检索或回答生成。 / Verifies retrieval and answer generation are skipped when no versions are readable."""

    vector_repository = FakeVectorRepository([make_chunk()])
    answer_generator = FakeAnswerGenerator()
    service = RagService(
        authorization_service=FakeAuthorizationService(frozenset()),
        vector_repository=vector_repository,
        answer_generator=answer_generator,
    )

    result = service.answer("秘密规则是什么？", CurrentUser(user_id="U001"))

    assert result == RagAnswerResponse(
        answer=NO_EVIDENCE_MESSAGE,
        evidence_found=False,
        sources=[],
    )
    assert vector_repository.calls == []
    assert answer_generator.calls == []


def test_answer_returns_no_evidence_when_retrieval_is_empty() -> None:
    """验证检索为空时拒绝猜测并跳过回答生成。 / Verifies empty retrieval refuses guessing and skips answer generation."""

    vector_repository = FakeVectorRepository([])
    answer_generator = FakeAnswerGenerator()
    service = RagService(
        authorization_service=FakeAuthorizationService(frozenset({"DOC-V1"})),
        vector_repository=vector_repository,
        answer_generator=answer_generator,
    )

    result = service.answer("未知规则？", CurrentUser(user_id="U001"))

    assert result.evidence_found is False
    assert result.sources == []
    assert answer_generator.calls == []


def test_answer_returns_no_evidence_below_score_threshold() -> None:
    """验证相关度不足时不把低质量片段交给回答生成器。 / Verifies low-relevance chunks are not sent to the answer generator."""

    vector_repository = FakeVectorRepository([make_chunk(score=0.49)])
    answer_generator = FakeAnswerGenerator()
    service = RagService(
        authorization_service=FakeAuthorizationService(
            frozenset({"TRAVEL_POLICY-V2"})
        ),
        vector_repository=vector_repository,
        answer_generator=answer_generator,
        minimum_score=0.5,
    )

    result = service.answer("完全无关的问题", CurrentUser(user_id="U001"))

    assert result.evidence_found is False
    assert result.answer == NO_EVIDENCE_MESSAGE
    assert answer_generator.calls == []
