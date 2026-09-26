"""显式运行真实模型的同一份 24 题评测。 / Opt-in real-provider corpus evaluation."""

import json
import os
import sys
from typing import Any

from app.dependencies import (
    build_answer_generator,
    build_embedding_provider,
    get_rag_minimum_score,
)
from app.evaluation.corpus_suite import run_corpus_evaluation


class CachingEmbeddingProvider:
    """仅在单次评测内复用相同文本的向量。 / Caches repeated texts for one evaluation."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self._cache: dict[str, list[float]] = {}
        self.index_identity = delegate.index_identity

    def embed(self, texts: list[str]) -> list[list[float]]:
        """只把尚未出现的文本发送给真实 Provider。 / Sends only cache misses."""
        missing_texts: list[str] = []
        for text in texts:
            if text not in self._cache and text not in missing_texts:
                missing_texts.append(text)
        if missing_texts:
            missing_vectors = self._delegate.embed(missing_texts)
            for text, vector in zip(missing_texts, missing_vectors, strict=True):
                self._cache[text] = vector
        return [self._cache[text] for text in texts]


def main() -> None:
    """仅在用户开启开关后调用云端，绝不输出密钥。 / Calls cloud only when opted in."""
    if os.getenv("RUN_REAL_RAG_EVALUATION") != "1":
        raise SystemExit("Set RUN_REAL_RAG_EVALUATION=1 to allow paid provider calls")
    embedding_mode = os.getenv("RAG_EMBEDDING_MODE", "").strip().lower()
    if embedding_mode not in ("gemini", "dashscope"):
        raise SystemExit(
            "Set RAG_EMBEDDING_MODE=gemini or dashscope for real evaluation"
        )
    embedding_provider = CachingEmbeddingProvider(build_embedding_provider())
    report = run_corpus_evaluation(
        embedding_provider=embedding_provider,
        answer_generator=build_answer_generator(),
        minimum_score=get_rag_minimum_score(),
    )
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
