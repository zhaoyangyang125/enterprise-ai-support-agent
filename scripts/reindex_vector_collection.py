"""把旧 Collection 的 Chunk 重新向量化到独立新索引(可分批、可续传)。 / Re-embeds chunks into a new index (batched, resumable).

Usage (repo root, venv active; embedding env vars set, key only via DASHSCOPE_API_KEY):
    RUN_VECTOR_REINDEX=1 python -m scripts.reindex_vector_collection --limit 5     # trial run
    RUN_VECTOR_REINDEX=1 python -m scripts.reindex_vector_collection               # the rest (already stored IDs are skipped)
"""

import argparse
import os
import time
from dataclasses import dataclass
from pathlib import Path

from app.dependencies import build_embedding_provider
from app.repositories.vector_repository import ChromaVectorRepository
from app.schemas.rag import IndexedChunk
from app.services.embedding_service import HashEmbeddingProvider
from app.services.rag_provider_errors import RagProviderError


@dataclass
class ReindexReport:
    """一次迁移的结果统计。 / Outcome counts of one run."""

    succeeded: int = 0
    skipped: int = 0
    failed: int = 0
    stopped_reason: str | None = None


def reindex(
    chunks: list[IndexedChunk],
    target: ChromaVectorRepository,
    batch_size: int = 10,
    limit: int | None = None,
    pause_seconds: float = 0.0,
) -> ReindexReport:
    """已存在的 Chunk ID 跳过；接口出错时在该批次停止，不无限重试。
    Skips IDs already stored; on a provider error stops at that batch (no endless retry)."""
    report = ReindexReport()
    stored = target.existing_chunk_ids()
    pending = [chunk for chunk in chunks if chunk.chunk_id not in stored]
    report.skipped = len(chunks) - len(pending)
    if limit is not None:
        pending = pending[:limit]
    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        try:
            target.upsert_chunks(batch)
        except RagProviderError as error:
            report.failed = len(pending) - start
            report.stopped_reason = str(error)
            break
        report.succeeded += len(batch)
        if pause_seconds and start + batch_size < len(pending):
            time.sleep(pause_seconds)
    return report


def main() -> None:
    """显式执行迁移，不修改旧索引或业务数据库。 / Runs an opt-in non-destructive migration."""
    if os.getenv("RUN_VECTOR_REINDEX") != "1":
        raise SystemExit("Set RUN_VECTOR_REINDEX=1 to allow vector reindexing")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only embed this many new chunks (trial run)")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--pause", type=float, default=0.5, help="seconds between batches")
    args = parser.parse_args()

    source_path = Path(os.getenv("SOURCE_VECTOR_PATH", "chroma_data"))
    source_collection = os.getenv("SOURCE_VECTOR_COLLECTION", "enterprise_documents")
    target_path = Path(os.getenv("RAG_VECTOR_PATH", "chroma_data_dashscope"))
    target_collection = os.getenv(
        "RAG_VECTOR_COLLECTION",
        "enterprise_documents_text_embedding_v4_1024",
    )
    if source_path.resolve() == target_path.resolve():
        if source_collection == target_collection:
            raise SystemExit("Source and target vector collections must be different")

    source = ChromaVectorRepository.persistent(
        path=source_path,
        collection_name=source_collection,
        embedding_provider=HashEmbeddingProvider(),
    )
    chunks = source.list_all_chunks()
    if not chunks:
        raise SystemExit("Source vector collection is empty")

    provider = build_embedding_provider()
    target = ChromaVectorRepository.persistent(
        path=target_path,
        collection_name=target_collection,
        embedding_provider=provider,
    )
    report = reindex(chunks, target, args.batch_size, args.limit, args.pause)

    print(f"source chunks={len(chunks)} succeeded={report.succeeded} "
          f"skipped(already stored)={report.skipped} failed={report.failed}")
    print(f"tokens used this run={getattr(provider, 'total_tokens', 'n/a')}")
    print(f"Source preserved: {source_path} / {source_collection}")
    print(f"Target: {target_path} / {target_collection} (records now: {len(target.existing_chunk_ids())})")
    if report.stopped_reason:
        raise SystemExit(f"Stopped on provider error: {report.stopped_reason} (rerun to resume)")


if __name__ == "__main__":
    main()
