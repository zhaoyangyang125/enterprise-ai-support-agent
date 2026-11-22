from app.repositories.vector_repository import ChromaVectorRepository
from app.schemas.rag import IndexedChunk
from app.services.embedding_service import HashEmbeddingProvider
from app.services.rag_provider_errors import RagProviderError
from scripts.reindex_vector_collection import reindex


def _chunks(n: int) -> list[IndexedChunk]:
    return [
        IndexedChunk(chunk_id=f"C{i}", document_id="D", document_version_id="V",
                     content=f"text {i}", source_name="s.pdf", page=i)
        for i in range(n)
    ]


def _target(tmp_path) -> ChromaVectorRepository:
    return ChromaVectorRepository.persistent(tmp_path, "reindex_target", HashEmbeddingProvider())


def test_limit_then_resume_skips_stored_chunks(tmp_path) -> None:
    target = _target(tmp_path)
    chunks = _chunks(7)

    first = reindex(chunks, target, batch_size=2, limit=3)
    second = reindex(chunks, target, batch_size=2)

    assert (first.succeeded, first.skipped) == (3, 0)
    assert (second.succeeded, second.skipped) == (4, 3)
    assert len(target.existing_chunk_ids()) == 7


def test_provider_error_stops_without_retrying_and_keeps_stored(tmp_path) -> None:
    target = _target(tmp_path)
    calls = {"n": 0}
    real_upsert = target.upsert_chunks

    def flaky(batch):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RagProviderError("rag_provider_http_403_AllocationQuota.FreeTierOnly")
        real_upsert(batch)

    target.upsert_chunks = flaky  # type: ignore[method-assign]
    report = reindex(_chunks(6), target, batch_size=2)

    assert report.succeeded == 2
    assert report.failed == 4
    assert "403" in (report.stopped_reason or "")
    assert calls["n"] == 2
    assert len(target.existing_chunk_ids()) == 2
