from app.repositories.vector_repository import ChromaVectorRepository
from app.schemas.rag import IndexedChunk, RetrievalFilter
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


def test_chroma_combines_authorization_with_metadata_filters(tmp_path) -> None:
    """验证 Chroma 使用 AND 同时执行版本权限与结构 metadata 过滤。 / Verifies Chroma combines version authorization and structural metadata filters with AND."""

    repository = ChromaVectorRepository.persistent(
        path=tmp_path / "chroma",
        collection_name="filtered_documents",
        embedding_provider=HashEmbeddingProvider(dimensions=64),
    )
    repository.upsert_chunks(
        [
            IndexedChunk(
                chunk_id="ALLOWED-PDF",
                document_id="POLICY",
                document_version_id="ALLOWED-PDF-V1",
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
                cell_range="A4:F8",
            ),
            IndexedChunk(
                chunk_id="SECRET-XLSX",
                document_id="SECRET",
                document_version_id="SECRET-V1",
                content="動画画面遷移は禁止",
                source_name="secret.xlsx",
                content_type="table",
                sheet="画面遷移",
                cell_range="A1:F3",
            ),
        ]
    )

    result = repository.search(
        query="動画画面遷移",
        allowed_document_version_ids=frozenset(
            {"ALLOWED-PDF-V1", "ALLOWED-XLSX-V1"}
        ),
        limit=5,
        metadata_filter=RetrievalFilter(
            content_types=frozenset({"table"}),
            sheets=frozenset({"画面遷移"}),
        ),
    )

    assert [chunk.chunk_id for chunk in result] == ["ALLOWED-XLSX"]


def test_chroma_round_trips_image_evidence_metadata(tmp_path) -> None:
    """验证 Chroma 只保存可检索的图片 metadata，并能完整恢复。 / Verifies Chroma stores and restores only searchable image metadata."""

    repository = ChromaVectorRepository.persistent(
        path=tmp_path / "chroma",
        collection_name="image_evidence",
        embedding_provider=HashEmbeddingProvider(dimensions=64),
    )
    repository.upsert_chunks(
        [
            IndexedChunk(
                chunk_id="IMAGE-001",
                document_id="HMI-MANUAL",
                document_version_id="HMI-MANUAL-V1",
                content="仪表盘显示红色制动警告灯",
                source_name="hmi_manual.pdf",
                content_type="note",
                modality="image",
                extraction_method="vision",
                image_id="IMG-HMI-001",
                image_index=2,
                mime_type="image/png",
                confidence=0.91,
                page=7,
            )
        ]
    )

    result = repository.search(
        "红色制动警告灯",
        frozenset({"HMI-MANUAL-V1"}),
        1,
    )

    assert len(result) == 1
    assert result[0].modality == "image"
    assert result[0].extraction_method == "vision"
    assert result[0].image_id == "IMG-HMI-001"
    assert result[0].image_index == 2
    assert result[0].mime_type == "image/png"
    assert result[0].confidence == 0.91
    stored_metadata = repository._collection.get(ids=["IMAGE-001"])["metadatas"][0]
    assert "image_path" not in stored_metadata
    assert "image_url" not in stored_metadata
