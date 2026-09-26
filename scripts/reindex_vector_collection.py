"""把旧 Collection 的 Chunk 重新向量化到独立新索引。 / Re-embeds chunks into a new index."""

import os
from pathlib import Path

from app.dependencies import build_embedding_provider
from app.repositories.vector_repository import ChromaVectorRepository
from app.services.embedding_service import HashEmbeddingProvider


def main() -> None:
    """显式执行迁移，不修改旧索引或业务数据库。 / Runs an opt-in non-destructive migration."""
    if os.getenv("RUN_VECTOR_REINDEX") != "1":
        raise SystemExit("Set RUN_VECTOR_REINDEX=1 to allow vector reindexing")

    source_path = Path(os.getenv("SOURCE_VECTOR_PATH", "chroma_data"))
    source_collection = os.getenv(
        "SOURCE_VECTOR_COLLECTION",
        "enterprise_documents",
    )
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

    target = ChromaVectorRepository.persistent(
        path=target_path,
        collection_name=target_collection,
        embedding_provider=build_embedding_provider(),
    )
    target.upsert_chunks(chunks)

    target_chunks = target.list_all_chunks()
    if len(target_chunks) != len(chunks):
        raise RuntimeError("Target chunk count does not match source chunk count")
    print(f"Vector reindex completed: {len(chunks)} chunks")
    print(f"Source preserved: {source_path} / {source_collection}")
    print(f"Target created: {target_path} / {target_collection}")


if __name__ == "__main__":
    main()
