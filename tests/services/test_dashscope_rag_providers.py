import json

import httpx
import pytest

from app.dependencies import (
    build_answer_generator,
    build_embedding_provider,
    get_vector_repository,
    get_rag_minimum_score,
)
from app.schemas.rag import RetrievedChunk
from app.services.dashscope_rag_providers import (
    DashScopeEmbeddingProvider,
    QwenAnswerGenerator,
)
from app.services.rag_provider_errors import RagProviderError
from app.evaluation.real_provider_suite import CachingEmbeddingProvider


def _evidence() -> RetrievedChunk:
    """创建一条已授权证据。 / Creates one authorized evidence chunk."""
    return RetrievedChunk(
        chunk_id="C1",
        document_id="D1",
        document_version_id="V1",
        content="出張時の食事代上限は3000円です。",
        score=0.9,
        source_name="travel_policy.pdf",
        page=2,
    )


def test_dashscope_embedding_batches_and_restores_response_order() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        data: list[dict[str, object]] = []
        for index, text in enumerate(payload["input"]):
            data.append({"index": index, "embedding": [float(ord(text))] * 8})
        data.reverse()
        return httpx.Response(200, json={"data": data})

    provider = DashScopeEmbeddingProvider(
        api_key="secret",
        model_name="text-embedding-v4",
        dimensions=8,
        transport=httpx.MockTransport(respond),
        batch_size=2,
    )
    result = provider.embed(["A", "B", "C"])

    assert [vector[0] for vector in result] == [65.0, 66.0, 67.0]
    assert len(requests) == 2
    assert requests[0].url.path.endswith("/embeddings")
    assert requests[0].headers["Authorization"] == "Bearer secret"
    assert "secret" not in str(requests[0].url)


def test_dashscope_embedding_rejects_wrong_dimension() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [1.0]}]},
        )
    )
    provider = DashScopeEmbeddingProvider(
        "secret", "text-embedding-v4", 8, transport=transport
    )
    with pytest.raises(RagProviderError, match="rag_embedding_dimension_mismatch"):
        provider.embed(["test"])


def test_qwen_answer_contains_evidence_but_not_backend_citation_metadata() -> None:
    sent_payloads: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent_payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "上限は3000円です。"},
                    }
                ]
            },
        )

    generator = QwenAnswerGenerator(
        "secret", "qwen-plus", transport=httpx.MockTransport(respond)
    )
    answer = generator.generate("出張中の食事代はいくらですか？", [_evidence()])

    assert answer == "上限は3000円です。"
    serialized = json.dumps(sent_payloads[0], ensure_ascii=False)
    assert "出張時の食事代上限は3000円です。" in serialized
    assert "travel_policy.pdf" not in serialized
    assert "Do not output citations" in serialized


@pytest.mark.parametrize("status_code", [429, 500])
def test_qwen_failure_is_sanitized(status_code: int) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code, text="secret prompt and credential")
    )
    generator = QwenAnswerGenerator("secret", "qwen-plus", transport=transport)
    with pytest.raises(RagProviderError) as caught:
        generator.generate("question", [_evidence()])
    assert str(caught.value) == f"rag_provider_http_{status_code}_unknown"
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        ({"code": "InvalidParameter", "message": "private content"}, "InvalidParameter"),
        ({"error": {"code": "model_not_found", "message": "private"}}, "model_not_found"),
    ],
)
def test_dashscope_extracts_only_safe_error_code(body, expected_code) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(400, json=body)
    )
    provider = DashScopeEmbeddingProvider(
        "secret", "text-embedding-v4", 8, transport=transport
    )
    with pytest.raises(RagProviderError) as caught:
        provider.embed(["private document content"])
    assert str(caught.value) == f"rag_provider_http_400_{expected_code}"
    assert "private" not in str(caught.value)


def test_dashscope_retries_temporary_connection_failure() -> None:
    """临时断线后重试成功，不对调用方暴露第一次故障。 / Retries a transient disconnect."""
    call_count = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.RemoteProtocolError("temporary disconnect")
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [1.0] * 8}]},
        )

    provider = DashScopeEmbeddingProvider(
        "secret", "text-embedding-v4", 8, transport=httpx.MockTransport(respond)
    )
    assert provider.embed(["test"])[0] == [1.0] * 8
    assert call_count == 2


def test_real_evaluation_cache_avoids_duplicate_embedding_calls() -> None:
    """同一次评测中的重复问题只调用Provider一次。 / Caches duplicate queries."""
    class FakeEmbedding:
        index_identity = "fake:8"

        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def embed(self, texts: list[str]) -> list[list[float]]:
            self.calls.append(list(texts))
            return [[float(len(text))] * 8 for text in texts]

    delegate = FakeEmbedding()
    provider = CachingEmbeddingProvider(delegate)
    first = provider.embed(["A", "B"])
    second = provider.embed(["B", "C", "A"])

    assert delegate.calls == [["A", "B"], ["C"]]
    assert second[0] == first[1]


def test_dashscope_dependency_selection(monkeypatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "secret")
    monkeypatch.setenv("RAG_EMBEDDING_MODE", "dashscope")
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "text-embedding-v4")
    monkeypatch.setenv("RAG_EMBEDDING_DIMENSIONS", "1024")
    monkeypatch.setenv("RAG_ANSWER_MODE", "qwen")
    monkeypatch.setenv("RAG_ANSWER_MODEL", "qwen-plus")

    embedding = build_embedding_provider()
    answer = build_answer_generator()

    assert isinstance(embedding, DashScopeEmbeddingProvider)
    assert embedding.index_identity == "dashscope:text-embedding-v4:1024"
    assert isinstance(answer, QwenAnswerGenerator)


def test_dashscope_mode_requires_key(monkeypatch) -> None:
    monkeypatch.setenv("RAG_EMBEDDING_MODE", "dashscope")
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "text-embedding-v4")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        build_embedding_provider()


def test_vector_path_and_collection_can_be_isolated(monkeypatch, tmp_path) -> None:
    """真实模型可使用新目录，不覆盖默认 Hash 索引。 / Supports a parallel index."""
    vector_path = tmp_path / "parallel_chroma"
    monkeypatch.setenv("RAG_EMBEDDING_MODE", "hash")
    monkeypatch.setenv("RAG_VECTOR_PATH", str(vector_path))
    monkeypatch.setenv("RAG_VECTOR_COLLECTION", "parallel_documents")
    get_vector_repository.cache_clear()
    try:
        repository = get_vector_repository()
        assert repository._collection.name == "parallel_documents"
        assert vector_path.exists()
    finally:
        get_vector_repository.cache_clear()


def test_rag_minimum_score_comes_from_environment(monkeypatch) -> None:
    """真实模型阈值可校准，默认行为仍保持0.25。 / Makes the gate configurable."""
    monkeypatch.delenv("RAG_MINIMUM_SCORE", raising=False)
    assert get_rag_minimum_score() == 0.25
    monkeypatch.setenv("RAG_MINIMUM_SCORE", "0.36")
    assert get_rag_minimum_score() == 0.36
    monkeypatch.setenv("RAG_MINIMUM_SCORE", "1.5")
    with pytest.raises(ValueError, match="between 0 and 1"):
        get_rag_minimum_score()
