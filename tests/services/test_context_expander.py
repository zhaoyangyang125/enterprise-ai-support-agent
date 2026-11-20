from app.auth.context import CurrentUser
from app.schemas.rag import IndexedChunk, RetrievedChunk
from app.services.context_expander import ContextExpander
from app.services.rag_service import NO_EVIDENCE_MESSAGE, RagService

ALLOWED = frozenset({"V1"})


def indexed(chunk_id: str, index: int, heading: str | None = None, section_no: str = "5-3") -> IndexedChunk:
    return IndexedChunk(chunk_id=chunk_id, document_id="D", document_version_id="V1", content=f"c-{chunk_id}",
                        source_name="m.pdf", chunk_index=index, section_no=section_no, heading=heading,
                        page=index, section=f"{section_no}. x")


def hit(heading: str | None = "H", refs: str | None = None) -> RetrievedChunk:
    base = indexed("HIT", 10, heading)
    return RetrievedChunk(**base.model_dump() | {"refs": refs}, score=0.8)


class FakeRepo:
    def __init__(self, neighbors=(), referenced=()):
        self._neighbors, self._referenced = list(neighbors), list(referenced)

    def get_neighbors(self, chunk, allowed, window=1):
        return self._neighbors

    def get_referenced(self, chunk, allowed):
        return self._referenced


def test_expander_adds_neighbors_and_references_with_lower_score():
    repo = FakeRepo([indexed("N1", 9, "H")], [indexed("R1", 40)])
    extras = ContextExpander(repo, max_referenced_per_hit=2).expand([hit()], ALLOWED)
    assert [e.chunk_id for e in extras] == ["N1", "R1"]
    assert all(e.score < 0.8 for e in extras)


def test_expander_does_not_follow_references_by_default():
    repo = FakeRepo([], [indexed("R1", 40)])
    assert ContextExpander(repo).expand([hit()], ALLOWED) == []


def test_expander_skips_neighbors_with_a_different_heading_and_duplicates():
    repo = FakeRepo([indexed("N1", 9, "OTHER"), indexed("HIT", 10, "H"), indexed("N2", 11, None)], [])
    extras = ContextExpander(repo).expand([hit()], ALLOWED)
    assert [e.chunk_id for e in extras] == ["N2"]


def test_expander_caps_extra_chunks():
    repo = FakeRepo([indexed(f"N{i}", i, "H") for i in range(8)], [])
    assert len(ContextExpander(repo, max_extra=3).expand([hit()], ALLOWED)) == 3


class _Auth:
    def __init__(self, allowed): self.allowed = allowed
    def get_readable_document_version_ids(self, user): return self.allowed


class _Search:
    def __init__(self, chunks): self.chunks = chunks
    def search(self, query, allowed_document_version_ids, limit, metadata_filter=None): return self.chunks


class _Gen:
    def __init__(self): self.evidence = None
    def generate(self, query, evidence):
        self.evidence = evidence
        return "ok"


USER = CurrentUser(user_id="U001", department_id="D")


def test_service_appends_support_chunks_only_after_evidence_gate():
    gen = _Gen()
    service = RagService(_Auth(ALLOWED), _Search([hit()]), gen, minimum_score=0.5,
                         context_expander=ContextExpander(FakeRepo([indexed("N1", 9, "H")], [])))
    result = service.answer("q", USER)
    assert [c.chunk_id for c in gen.evidence] == ["HIT", "N1"]
    assert result.evidence_found is True


def test_service_does_not_expand_when_there_is_no_evidence():
    weak = RetrievedChunk(**hit().model_dump() | {"score": 0.1})
    service = RagService(_Auth(ALLOWED), _Search([weak]), _Gen(), minimum_score=0.5,
                         context_expander=ContextExpander(FakeRepo([indexed("N1", 9, "H")], [])))
    result = service.answer("q", USER)
    assert result.evidence_found is False and result.answer == NO_EVIDENCE_MESSAGE


def test_service_drops_support_chunks_outside_authorized_versions():
    foreign = indexed("X", 9, "H").model_copy(update={"document_version_id": "SECRET"})
    gen = _Gen()
    service = RagService(_Auth(ALLOWED), _Search([hit()]), gen, minimum_score=0.5,
                         context_expander=ContextExpander(FakeRepo([foreign], [])))
    service.answer("q", USER)
    assert [c.chunk_id for c in gen.evidence] == ["HIT"]
