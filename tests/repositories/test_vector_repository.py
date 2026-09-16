from app.repositories.vector_repository import InMemoryVectorRepository
from app.schemas.rag import IndexedChunk, RetrievalFilter


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


def test_search_combines_authorization_and_metadata_filter() -> None:
    """验证 metadata 条件只能缩小权限允许的候选集合。 / Verifies metadata conditions can only narrow the authorized candidate set."""

    repository = InMemoryVectorRepository(
        [
            IndexedChunk(
                chunk_id="ALLOWED-PDF",
                document_id="POLICY",
                document_version_id="ALLOWED-V1",
                content="動画画面遷移は禁止",
                source_name="policy.pdf",
                page=2,
            ),
            IndexedChunk(
                chunk_id="ALLOWED-XLSX",
                document_id="SPEC",
                document_version_id="ALLOWED-XLSX-V1",
                content="動画画面遷移は禁止",
                source_name="spec.xlsx",
                content_type="table",
                sheet="画面遷移",
            ),
            IndexedChunk(
                chunk_id="SECRET-XLSX",
                document_id="SECRET",
                document_version_id="SECRET-V1",
                content="動画画面遷移は禁止",
                source_name="secret.xlsx",
                content_type="table",
                sheet="画面遷移",
            ),
        ]
    )

    result = repository.search(
        query="動画画面遷移",
        allowed_document_version_ids=frozenset(
            {"ALLOWED-V1", "ALLOWED-XLSX-V1"}
        ),
        limit=5,
        metadata_filter=RetrievalFilter(
            content_types=frozenset({"table"}),
            sheets=frozenset({"画面遷移"}),
        ),
    )

    assert [chunk.chunk_id for chunk in result] == ["ALLOWED-XLSX"]
