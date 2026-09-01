from app.repositories.vector_repository import InMemoryVectorRepository
from app.schemas.rag import IndexedChunk


def make_chunk(version_id: str, content: str) -> IndexedChunk:
    """创建用于本地检索测试的文档片段。 / Creates a document chunk for local retrieval tests."""

    return IndexedChunk(
        chunk_id=f"CHUNK-{version_id}",
        document_id=f"DOC-{version_id}",
        document_version_id=version_id,
        content=content,
        source_name=f"{version_id}.pdf",
    )


def test_search_excludes_unauthorized_chunk_before_ranking() -> None:
    """验证本地检索层不会返回权限范围外的高相似度片段。 / Verifies local retrieval never returns a highly similar unauthorized chunk."""

    repository = InMemoryVectorRepository(
        [
            make_chunk("ALLOWED-V1", "一般的国内出差规定。"),
            make_chunk("SECRET-V1", "国内出差住宿费上限是秘密金额。"),
        ]
    )

    result = repository.search(
        query="国内出差住宿费上限",
        allowed_document_version_ids=frozenset({"ALLOWED-V1"}),
        limit=5,
    )

    assert [chunk.document_version_id for chunk in result] == ["ALLOWED-V1"]
