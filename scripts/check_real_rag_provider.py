"""执行一次不写入数据库的真实 Provider 最小检查。 / Runs one non-persistent provider smoke test."""

import os
import sys

from app.dependencies import build_answer_generator, build_embedding_provider
from app.schemas.rag import RetrievedChunk


def main() -> None:
    """验证一个向量和一个证据回答；必须显式允许外部调用。 / Runs two opt-in calls."""
    if os.getenv("RUN_REAL_RAG_SMOKE_TEST") != "1":
        raise SystemExit("Set RUN_REAL_RAG_SMOKE_TEST=1 to allow provider calls")

    embedding_provider = build_embedding_provider()
    vectors = embedding_provider.embed(["車載HMIの安全規定"])
    if len(vectors) != 1:
        raise RuntimeError("The embedding provider returned an unexpected count")

    answer_generator = build_answer_generator()
    evidence = RetrievedChunk(
        chunk_id="SMOKE-001",
        document_id="SMOKE-DOC",
        document_version_id="SMOKE-V1",
        content="出張時の食事代上限は3000円です。",
        score=1.0,
        source_name="smoke_test.txt",
    )
    answer = answer_generator.generate(
        "出張中の食事代はいくらですか？",
        [evidence],
    )

    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Embedding OK: count=1, dimensions={len(vectors[0])}")
    print(f"Answer OK: {answer}")


if __name__ == "__main__":
    main()
