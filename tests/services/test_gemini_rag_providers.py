import json

import httpx
import pytest

from app.auth.context import CurrentUser
from app.dependencies import build_answer_generator, build_embedding_provider
from app.schemas.rag import RetrievedChunk
from app.services.gemini_rag_providers import GeminiAnswerGenerator, GeminiEmbeddingProvider
from app.services.rag_provider_errors import RagProviderError
from app.services.rag_service import RagService


def _evidence() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="C1",
        document_id="D1",
        document_version_id="V1",
        content="休暇の残日数は8日です。",
        score=0.8,
        source_name="policy.pdf",
        page=2,
    )


def test_embedding_batches_in_order_and_uses_secret_header() -> None:
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        payload = json.loads(request.content)
        values = []
        for item in payload["requests"]:
            text = item["content"]["parts"][0]["text"]
            values.append({"values": [float(ord(text)), 1.0] * 4})
        return httpx.Response(200, json={"embeddings": values})

    provider = GeminiEmbeddingProvider(
        "secret", "gemini-embedding-001", 8,
        transport=httpx.MockTransport(respond), batch_size=2,
    )
    result = provider.embed(["A", "B", "C"])

    assert [vector[0] for vector in result] == [65.0, 66.0, 67.0]
    assert len(calls) == 2
    assert calls[0].headers["x-goog-api-key"] == "secret"
    assert "secret" not in str(calls[0].url)


def test_embedding_rejects_wrong_dimension_and_does_not_fallback() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"embeddings": [{"values": [1.0]}]})
    )
    provider = GeminiEmbeddingProvider("secret", "model", 8, transport=transport)
    with pytest.raises(RagProviderError, match="rag_embedding_dimension_mismatch"):
        provider.embed(["test"])


def test_answer_uses_only_passed_evidence_and_not_model_citations() -> None:
    sent: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.content.decode("utf-8"))
        return httpx.Response(200, json={"candidates": [{
            "finishReason": "STOP", "content": {"parts": [{"text": "残りは8日です。"}]}
        }]})

    generator = GeminiAnswerGenerator("secret", "model", transport=httpx.MockTransport(respond))
    assert generator.generate("休暇は何日残っていますか？", [_evidence()]) == "残りは8日です。"
    assert "休暇の残日数は8日です。" in sent[0]
    assert "Do not create citations" in sent[0]
    assert "policy.pdf" not in sent[0]


@pytest.mark.parametrize("status_code", [429, 500])
def test_answer_sanitizes_http_failure(status_code: int) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code, text="private prompt and secret")
    )
    generator = GeminiAnswerGenerator("secret", "model", transport=transport)
    with pytest.raises(RagProviderError) as caught:
        generator.generate("question", [_evidence()])
    assert str(caught.value) == f"rag_provider_http_{status_code}"
    assert "private prompt" not in str(caught.value)
    assert "secret" not in str(caught.value)


def test_answer_timeout_is_sanitized() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private timeout detail", request=request)

    generator = GeminiAnswerGenerator("secret", "model", transport=httpx.MockTransport(timeout))
    with pytest.raises(RagProviderError, match="rag_provider_timeout"):
        generator.generate("question", [_evidence()])


def test_answer_rejects_invalid_response() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"candidates": []}))
    generator = GeminiAnswerGenerator("secret", "model", transport=transport)
    with pytest.raises(RagProviderError, match="rag_answer_empty"):
        generator.generate("question", [_evidence()])


def test_no_evidence_does_not_call_provider() -> None:
    generator = GeminiAnswerGenerator("secret", "model", transport=httpx.MockTransport(
        lambda request: pytest.fail("Provider should not be called")))
    with pytest.raises(ValueError, match="Evidence is required"):
        generator.generate("question", [])


def test_acl_and_evidence_gate_skip_real_answer_provider() -> None:
    """没有授权或证据不足时，真实 LLM 也绝不被请求。 / ACL and gate prevent LLM calls."""
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    class Authorization:
        def __init__(self, allowed: frozenset[str]) -> None:
            self.allowed = allowed

        def get_readable_document_version_ids(self, current_user: CurrentUser) -> frozenset[str]:
            return self.allowed

    class Retrieval:
        def __init__(self, results: list[RetrievedChunk]) -> None:
            self.results = results
            self.calls = 0

        def search(self, query, allowed_document_version_ids, limit, metadata_filter=None):
            self.calls += 1
            return self.results

    generator = GeminiAnswerGenerator("secret", "model", transport=httpx.MockTransport(respond))
    retrieval = Retrieval([_evidence()])
    unauthorized = RagService(Authorization(frozenset()), retrieval, generator)
    assert unauthorized.answer("question", CurrentUser(user_id="U1")).evidence_found is False
    assert retrieval.calls == 0

    weak = _evidence().model_copy(update={"score": 0.1})
    retrieval.results = [weak]
    authorized = RagService(Authorization(frozenset({"V1"})), retrieval, generator)
    assert authorized.answer("question", CurrentUser(user_id="U1")).evidence_found is False
    assert requests == []


def test_unauthorized_chunk_never_enters_llm_prompt_or_citation() -> None:
    """即使 Repository 意外返回越权片段，Service 也只传授权证据。 / Defense in depth."""
    sent: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.content.decode("utf-8"))
        return httpx.Response(200, json={"candidates": [{
            "finishReason": "STOP", "content": {"parts": [{"text": "残りは8日です。"}]}
        }]})

    class Authorization:
        def get_readable_document_version_ids(self, current_user: CurrentUser) -> frozenset[str]:
            return frozenset({"V1"})

    class Retrieval:
        def search(self, query, allowed_document_version_ids, limit, metadata_filter=None):
            secret = _evidence().model_copy(update={
                "document_version_id": "SECRET-V1", "content": "secret document content",
                "source_name": "secret.pdf",
            })
            return [secret, _evidence()]

    generator = GeminiAnswerGenerator("secret", "model", transport=httpx.MockTransport(respond))
    service = RagService(Authorization(), Retrieval(), generator)
    answer = service.answer("休暇は何日？", CurrentUser(user_id="U1"))

    assert len(sent) == 1
    assert "secret document content" not in sent[0]
    assert "休暇の残日数は8日です。" in sent[0]
    assert [source.source_name for source in answer.sources] == ["policy.pdf"]


def test_default_modes_remain_offline(monkeypatch) -> None:
    monkeypatch.delenv("RAG_EMBEDDING_MODE", raising=False)
    monkeypatch.delenv("RAG_ANSWER_MODE", raising=False)
    assert build_embedding_provider().__class__.__name__ == "HashEmbeddingProvider"
    assert build_answer_generator().__class__.__name__ == "EvidenceOnlyAnswerGenerator"


def test_real_mode_requires_key_and_never_silently_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("RAG_EMBEDDING_MODE", "gemini")
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "model")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        build_embedding_provider()
