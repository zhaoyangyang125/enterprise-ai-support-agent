from app.repositories.vector_repository import ChromaVectorRepository
from app.schemas.rag import IndexedChunk
from app.services.embedding_service import HashEmbeddingProvider


def make_chunk(version_id: str, content: str, page: int) -> IndexedChunk:
    """创建带完整引用信息的 Chroma 测试 Chunk。 / Creates a Chroma test chunk with complete citation metadata."""

    return IndexedChunk(
        chunk_id=f"CHUNK-{version_id}",
        document_id=f"DOC-{version_id}",
        document_version_id=version_id,
        content=content,
        source_name=f"{version_id}.pdf",
        page=page,
        section="Policy",
    )


def test_chroma_search_filters_allowed_versions_inside_query(tmp_path) -> None:
    """验证 Chroma 在 query where 阶段排除更相似的越权版本。 / Verifies Chroma excludes a more-similar unauthorized version in the query where clause."""

    repository = ChromaVectorRepository.persistent(
        path=tmp_path / "chroma",
        collection_name="authorized_documents",
        embedding_provider=HashEmbeddingProvider(dimensions=64),
    )
    repository.upsert_chunks(
        [
            make_chunk("ALLOWED-V1", "国内出張の一般規定です。", 2),
            make_chunk("SECRET-V1", "国内出張の宿泊費上限は秘密金額です。", 9),
        ]
    )

    result = repository.search(
        query="国内出張の宿泊費上限",
        allowed_document_version_ids=frozenset({"ALLOWED-V1"}),
        limit=5,
    )

    assert [chunk.document_version_id for chunk in result] == ["ALLOWED-V1"]
    assert result[0].source_name == "ALLOWED-V1.pdf"
    assert result[0].page == 2


def test_chroma_persistent_client_loads_index_on_restart(tmp_path) -> None:
    """验证新 Repository 实例可以从本地目录重新加载索引。 / Verifies a new repository instance reloads the index from the local directory."""

    path = tmp_path / "chroma"
    embedding = HashEmbeddingProvider(dimensions=64)
    first = ChromaVectorRepository.persistent(path, "documents", embedding)
    first.upsert_chunks([make_chunk("DOC-V1", "休暇申請ルール", 4)])

    restarted = ChromaVectorRepository.persistent(path, "documents", embedding)
    result = restarted.search(
        "休暇申請ルール",
        frozenset({"DOC-V1"}),
        3,
    )

    assert len(result) == 1
    assert result[0].document_version_id == "DOC-V1"


def test_chroma_round_trips_structured_excel_citation_metadata(tmp_path) -> None:
    """验证 Chroma 保存并恢复结构类型和 Excel Cell Range。 / Verifies Chroma round-trips content type and Excel cell range."""

    repository = ChromaVectorRepository.persistent(
        path=tmp_path / "chroma",
        collection_name="structured_documents",
        embedding_provider=HashEmbeddingProvider(dimensions=64),
    )
    repository.upsert_chunks(
        [
            IndexedChunk(
                chunk_id="HMI-TABLE-001",
                document_id="HMI-SPEC",
                document_version_id="HMI-SPEC-V1",
                content="機能ID=HMI-AC-001; 期待結果=エアコン画面を表示",
                source_name="fictional_hmi_test_spec.xlsx",
                content_type="table",
                section="1. 基本機能テスト",
                sheet="機能仕様",
                cell_range="A8:H12",
                rows="10:12",
            )
        ]
    )

    result = repository.search(
        "HMI-AC-001 エアコン",
        frozenset({"HMI-SPEC-V1"}),
        1,
    )

    assert len(result) == 1
    assert result[0].content_type == "table"
    assert result[0].sheet == "機能仕様"
    assert result[0].cell_range == "A8:H12"
    assert result[0].rows == "10:12"
