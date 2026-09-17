from app.auth.context import CurrentUser
from app.schemas.rag import RagAnswerResponse, RetrievedChunk, RetrievalFilter
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
        self.calls: list[
            tuple[str, frozenset[str], int, RetrievalFilter | None]
        ] = []

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
        metadata_filter: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """记录检索条件并返回预设证据。 / Records retrieval parameters and returns preset evidence."""

        self.calls.append(
            (query, allowed_document_version_ids, limit, metadata_filter)
        )
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
        "location": "TravelPolicy_v2.pdf / Page 3",
        "score": 0.9,
        "content_type": "paragraph",
        "modality": "text",
        "extraction_method": None,
        "image_id": None,
        "image_url": None,
        "image_index": None,
        "mime_type": None,
        "confidence": None,
        "page": 3,
        "section": "2.1 国内出張",
        "sheet": None,
        "cell_range": None,
        "rows": None,
    }
    assert vector_repository.calls == [
        ("国内出差住宿费上限是多少？", frozenset({"TRAVEL_POLICY-V2"}), 5, None)
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


def test_answer_rejects_high_rrf_score_when_raw_signals_are_weak() -> None:
    """RRF排名高但原始相关性弱时拒答。 / Rejects high RRF rank with weak raw relevance."""
    irrelevant_chunk = make_chunk(score=0.5).model_copy(
        update={
            "content": "走行中は動画画面への遷移を禁止します。",
            "vector_score": 0.086,
            "keyword_score": 1.0,
            "keyword_match_ratio": 0.12,
        }
    )
    answer_generator = FakeAnswerGenerator()
    service = RagService(
        authorization_service=FakeAuthorizationService(
            frozenset({"TRAVEL_POLICY-V2"})
        ),
        vector_repository=FakeVectorRepository([irrelevant_chunk]),
        answer_generator=answer_generator,
    )

    result = service.answer(
        "会社では月面基地の駐車料金を毎月いくらまで精算できますか？",
        CurrentUser(user_id="U001"),
    )

    assert result.evidence_found is False
    assert result.answer == NO_EVIDENCE_MESSAGE
    assert result.sources == []
    assert answer_generator.calls == []


def test_answer_accepts_exact_keyword_evidence() -> None:
    """精确编号覆盖充分时保留证据。 / Accepts strong exact-keyword evidence."""
    exact_chunk = make_chunk(score=0.5).model_copy(
        update={
            "content": "TEST SAFETY CODE 7392",
            "vector_score": 0.1,
            "keyword_score": 1.0,
            "keyword_match_ratio": 1.0,
        }
    )
    answer_generator = FakeAnswerGenerator()
    service = RagService(
        authorization_service=FakeAuthorizationService(
            frozenset({"TRAVEL_POLICY-V2"})
        ),
        vector_repository=FakeVectorRepository([exact_chunk]),
        answer_generator=answer_generator,
    )

    result = service.answer(
        "TEST SAFETY CODE 7392",
        CurrentUser(user_id="U001"),
    )

    assert result.evidence_found is True
    assert len(answer_generator.calls) == 1


def test_answer_accepts_strong_semantic_evidence() -> None:
    """关键词覆盖较低时，强语义命中仍可回答。 / Accepts strong semantic evidence."""
    semantic_chunk = make_chunk(score=0.5).model_copy(
        update={
            "vector_score": 0.72,
            "keyword_score": 0.2,
            "keyword_match_ratio": 0.1,
        }
    )
    answer_generator = FakeAnswerGenerator()
    service = RagService(
        authorization_service=FakeAuthorizationService(
            frozenset({"TRAVEL_POLICY-V2"})
        ),
        vector_repository=FakeVectorRepository([semantic_chunk]),
        answer_generator=answer_generator,
    )

    result = service.answer(
        "国内出差のホテル代はいくらですか？",
        CurrentUser(user_id="U001"),
    )

    assert result.evidence_found is True
    assert len(answer_generator.calls) == 1


def test_answer_prefers_exact_excel_location_over_marginal_vector_match() -> None:
    """精确Excel定位优先于边缘语义命中。 / Prefers exact Excel location evidence."""
    marginal_vector_chunk = make_chunk(score=0.5).model_copy(
        update={
            "chunk_id": "UNRELATED-PDF",
            "content": "TEST SAFETY CODE 7392",
            "vector_score": 0.165,
            "keyword_match_ratio": None,
        }
    )
    exact_excel_chunk = make_chunk(score=0.5).model_copy(
        update={
            "chunk_id": "EXCEL-IMAGE",
            "content": "跨越海面的现代桥梁",
            "source_name": "fictional_bridge.xlsx",
            "sheet": "Sheet1",
            "cell_range": "C67:N88",
            "vector_score": None,
            "keyword_score": 1.0,
            "keyword_match_ratio": 1.0,
        }
    )
    answer_generator = FakeAnswerGenerator()
    service = RagService(
        authorization_service=FakeAuthorizationService(
            frozenset({"TRAVEL_POLICY-V2"})
        ),
        vector_repository=FakeVectorRepository(
            [marginal_vector_chunk, exact_excel_chunk]
        ),
        answer_generator=answer_generator,
    )

    result = service.answer(
        "Sheet1 C67:N88",
        CurrentUser(user_id="U001"),
    )

    passed_evidence = answer_generator.calls[0][1]
    assert [chunk.chunk_id for chunk in passed_evidence] == ["EXCEL-IMAGE"]
    assert result.sources[0].source_name == "fictional_bridge.xlsx"


def test_answer_passes_metadata_filter_and_refuses_when_no_result() -> None:
    """验证 metadata 条件传到 Repository，过滤后无结果时不调用回答生成器。 / Verifies metadata filters reach the repository and empty filtered results skip answer generation."""

    metadata_filter = RetrievalFilter(
        content_types=frozenset({"table"}),
        sheets=frozenset({"CAN信号"}),
    )
    vector_repository = FakeVectorRepository([])
    answer_generator = FakeAnswerGenerator()
    service = RagService(
        authorization_service=FakeAuthorizationService(
            frozenset({"HMI-SPEC-V1"})
        ),
        vector_repository=vector_repository,
        answer_generator=answer_generator,
    )

    result = service.answer(
        "VehicleSpeedの期待値",
        CurrentUser(user_id="U001"),
        metadata_filter,
    )

    assert result.evidence_found is False
    assert vector_repository.calls == [
        (
            "VehicleSpeedの期待値",
            frozenset({"HMI-SPEC-V1"}),
            5,
            metadata_filter,
        )
    ]
    assert answer_generator.calls == []


def test_citation_formats_excel_location_and_deduplicates_same_source() -> None:
    """验证 Excel Citation 显示 Sheet/Range，并对同一来源定位去重。 / Verifies Excel citations display sheet/range and deduplicate the same source location."""

    first = RetrievedChunk(
        chunk_id="XLSX-001-A",
        document_id="HMI-SPEC",
        document_version_id="HMI-SPEC-V1",
        content="HMI-AC-001 expectation",
        score=0.92,
        source_name="fictional_hmi_test_spec.xlsx",
        content_type="table",
        sheet="機能仕様",
        cell_range="A8:H12",
        rows="10:12",
    )
    duplicate_location = first.model_copy(
        update={"chunk_id": "XLSX-001-B", "content": "related row", "score": 0.8}
    )
    service = RagService(
        authorization_service=FakeAuthorizationService(
            frozenset({"HMI-SPEC-V1"})
        ),
        vector_repository=FakeVectorRepository([first, duplicate_location]),
        answer_generator=FakeAnswerGenerator(),
        minimum_score=0.5,
    )

    result = service.answer("HMI-AC-001", CurrentUser(user_id="U001"))

    assert len(result.sources) == 1
    assert result.sources[0].location == (
        "fictional_hmi_test_spec.xlsx / Sheet 機能仕様 / A8:H12"
    )
    assert result.sources[0].score == 0.92


def test_image_evidence_citation_exposes_safe_metadata_without_url_yet() -> None:
    """验证 Phase 1 的图片 Citation 返回安全 metadata，但暂不生成访问 URL。 / Verifies Phase 1 image citations expose safe metadata without generating a URL yet."""

    image_chunk = RetrievedChunk(
        chunk_id="IMAGE-001",
        document_id="HMI-MANUAL",
        document_version_id="HMI-MANUAL-V1",
        content="仪表盘显示红色制动警告灯",
        score=0.94,
        source_name="hmi_manual.pdf",
        content_type="note",
        modality="image",
        extraction_method="vision",
        image_id="img_" + "a" * 64,
        image_index=2,
        mime_type="image/png",
        confidence=0.91,
        page=7,
    )
    service = RagService(
        authorization_service=FakeAuthorizationService(
            frozenset({"HMI-MANUAL-V1"})
        ),
        vector_repository=FakeVectorRepository([image_chunk]),
        answer_generator=FakeAnswerGenerator(),
        minimum_score=0.5,
    )

    result = service.answer("制动警告灯", CurrentUser(user_id="U001"))

    citation = result.sources[0]
    assert citation.modality == "image"
    assert citation.extraction_method == "vision"
    assert citation.image_id == "img_" + "a" * 64
    assert citation.image_url == (
        "/api/documents/HMI-MANUAL/versions/HMI-MANUAL-V1/assets/img_" + "a" * 64
    )
    assert citation.confidence == 0.91
