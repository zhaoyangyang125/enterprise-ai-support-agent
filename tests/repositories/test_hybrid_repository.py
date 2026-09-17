"""Hybrid Search、BM25与RRF的离线测试。 / Offline hybrid search tests."""
import pytest

from app.repositories.hybrid_repository import (
    Bm25KeywordRetriever, HybridVectorRepository, InMemoryKeywordRepository,
    reciprocal_rank_fusion,
)
from app.schemas.rag import IndexedChunk, RetrievedChunk, RetrievalFilter


def chunk(chunk_id: str, content: str, version: str = "PUBLIC-V1", **metadata) -> IndexedChunk:
    """创建保留完整metadata的测试Chunk。 / Builds a test chunk."""
    return IndexedChunk(chunk_id=chunk_id, document_id=metadata.pop("document_id", "DOC"),
        document_version_id=version, content=content,
        source_name=metadata.pop("source_name", "fictional.pdf"), **metadata)


def retrieved(value: IndexedChunk, score: float) -> RetrievedChunk:
    """将索引Chunk转换成指定分数的结果。 / Creates a scored result."""
    return RetrievedChunk(**value.model_dump(), score=score)


class FixedRepository:
    """返回固定结果并记录安全参数。 / Returns fixed results and records scope."""
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, allowed_document_version_ids, limit, metadata_filter=None):
        self.calls.append((query, allowed_document_version_ids, limit, metadata_filter))
        return self.results[:limit]


def test_bm25_finds_exact_codes_and_location_metadata():
    """精确编号、Sheet和Cell Range可以通过关键词召回。 / Recalls exact identifiers."""
    values = [
        chunk("CODE", "Maximum speed 40 km/h", document_id="MAPLE-9063",
              source_name="safety.pdf", page=1, section="TEST SAFETY CODE 7392"),
        chunk("IMAGE", "跨越海面的现代桥梁", source_name="bridge.xlsx",
              modality="image", extraction_method="vision", image_id="img_" + "a" * 64,
              image_index=2, mime_type="image/png", sheet="Sheet1", cell_range="C67:N88"),
    ]
    repository = InMemoryKeywordRepository(values)
    for query, expected in [("MAPLE-9063", "CODE"), ("TEST SAFETY CODE 7392", "CODE"),
                            ("Sheet1 C67:N88", "IMAGE")]:
        result = repository.search(query, frozenset({"PUBLIC-V1"}), 2)
        assert result[0].chunk_id == expected


def test_keyword_acl_and_metadata_filter_are_applied_before_ranking():
    """秘密Chunk和不匹配Sheet不能进入BM25候选。 / Filters before BM25."""
    values = [
        chunk("PUBLIC", "MAPLE-9063", sheet="Allowed"),
        chunk("OTHER-SHEET", "MAPLE-9063", sheet="Other"),
        chunk("SECRET", "MAPLE-9063 exact secret", version="SECRET-V1", sheet="Allowed"),
    ]
    repository = InMemoryKeywordRepository(values)
    result = repository.search("MAPLE-9063", frozenset({"PUBLIC-V1"}), 5,
                               RetrievalFilter(sheets=frozenset({"Allowed"})))
    assert [item.chunk_id for item in result] == ["PUBLIC"]


def test_rrf_ranking_and_duplicate_removal():
    """两路共同命中的Chunk提升，并按ID去重。 / Rewards agreement and deduplicates."""
    a = chunk("A", "a")
    b = chunk("B", "b")
    c = chunk("C", "c")
    vector = [retrieved(a, 0.9), retrieved(b, 0.8), retrieved(c, 0.7)]
    keyword = [retrieved(c, 1.0), retrieved(a, 0.8), retrieved(c, 0.7)]
    result = reciprocal_rank_fusion([vector, keyword])
    assert [item.chunk_id for item in result] == ["A", "C", "B"]
    assert len({item.chunk_id for item in result}) == 3
    assert all(0 <= item.score <= 1 for item in result)


def test_rrf_preserves_raw_relevance_signals():
    """RRF只改变排序分数，并保留证据充分性所需信号。 / Preserves raw relevance signals."""
    value = chunk("A", "TEST SAFETY CODE 7392")
    vector_result = retrieved(value, 0.72).model_copy(
        update={"vector_score": 0.72}
    )
    keyword_result = retrieved(value, 1.0).model_copy(
        update={"keyword_score": 1.0, "keyword_match_ratio": 1.0}
    )

    result = reciprocal_rank_fusion([[vector_result], [keyword_result]])

    assert result[0].score == 1.0
    assert result[0].vector_score == 0.72
    assert result[0].keyword_score == 1.0
    assert result[0].keyword_match_ratio == 1.0


def test_bm25_reports_strong_coverage_for_exact_code_and_excel_location():
    """精确代码与Excel定位产生强关键词覆盖率。 / Reports strong exact-match coverage."""
    values = [
        chunk("CODE", "TEST SAFETY CODE 7392"),
        chunk("EXCEL", "image description", sheet="Sheet1", cell_range="C67:N88"),
    ]
    repository = InMemoryKeywordRepository(values)

    code_result = repository.search(
        "TEST SAFETY CODE 7392",
        frozenset({"PUBLIC-V1"}),
        2,
    )
    excel_result = repository.search(
        "Sheet1 C67:N88",
        frozenset({"PUBLIC-V1"}),
        2,
    )

    assert code_result[0].chunk_id == "CODE"
    assert code_result[0].keyword_match_ratio == 1.0
    assert excel_result[0].chunk_id == "EXCEL"
    assert excel_result[0].keyword_match_ratio == 1.0


@pytest.mark.parametrize("vector_ids,keyword_ids,expected", [
    (["A"], [], ["A"]), ([], ["B"], ["B"]), ([], [], []),
    (["A"], ["A"], ["A"]), (["A"], ["B"], ["A", "B"]),
])
def test_hybrid_supports_one_or_both_result_lists(vector_ids, keyword_ids, expected):
    """任一路为空都不会使另一条有效结果丢失。 / Supports empty branches."""
    values = {name: chunk(name, name) for name in ("A", "B")}
    vector = FixedRepository([retrieved(values[name], 0.9) for name in vector_ids])
    keyword = FixedRepository([retrieved(values[name], 1.0) for name in keyword_ids])
    repository = HybridVectorRepository(vector, keyword)
    result = repository.search("query", frozenset({"PUBLIC-V1"}), 5)
    assert [item.chunk_id for item in result] == expected


def test_hybrid_passes_identical_scope_and_defensively_removes_unsafe_results():
    """两路收到同一范围，恶意返回的越权结果仍被删除。 / Applies defense in depth."""
    public = chunk("PUBLIC", "query", sheet="Allowed")
    secret = chunk("SECRET", "query", version="SECRET-V1", sheet="Allowed")
    wrong_sheet = chunk("WRONG", "query", sheet="Other")
    vector = FixedRepository([retrieved(public, 0.9), retrieved(secret, 0.9)])
    keyword = FixedRepository([retrieved(wrong_sheet, 1.0), retrieved(public, 0.8)])
    metadata_filter = RetrievalFilter(sheets=frozenset({"Allowed"}))
    repository = HybridVectorRepository(vector, keyword)
    result = repository.search("query", frozenset({"PUBLIC-V1"}), 2, metadata_filter)
    assert [item.chunk_id for item in result] == ["PUBLIC"]
    assert vector.calls[0][1:] == (frozenset({"PUBLIC-V1"}), 8, metadata_filter)
    assert keyword.calls[0][1:] == (frozenset({"PUBLIC-V1"}), 8, metadata_filter)


def test_hybrid_preserves_image_and_citation_metadata():
    """融合只更新score，不丢失图片与定位字段。 / Preserves evidence metadata."""
    image = chunk("IMAGE", "现代桥梁", source_name="bridge.xlsx", content_type="paragraph",
                  modality="image", extraction_method="vision", image_id="img_" + "b" * 64,
                  image_index=2, mime_type="image/png", confidence=0.95,
                  page=3, sheet="Sheet1", cell_range="C67:N88", rows="67:88")
    vector = FixedRepository([retrieved(image, 0.9)])
    keyword = FixedRepository([retrieved(image, 1.0)])
    result = HybridVectorRepository(vector, keyword).search(
        "跨越海面的现代桥梁", frozenset({"PUBLIC-V1"}), 1)
    fused = result[0]
    assert fused.image_id == image.image_id
    assert fused.page == 3
    assert fused.sheet == "Sheet1"
    assert fused.cell_range == "C67:N88"
    assert fused.confidence == 0.95


def test_bm25_empty_and_invalid_rrf_configuration():
    """空查询返回空结果，错误RRF参数明确失败。 / Handles empty inputs."""
    assert Bm25KeywordRetriever().rank("", [chunk("A", "text")], 5) == []
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([], rrf_k=0)
