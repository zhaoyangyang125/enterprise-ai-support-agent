"""验证Chroma Keyword分支复用授权where和完整metadata。 / Tests Chroma-backed keyword retrieval."""
from app.repositories.hybrid_repository import ChromaKeywordRepository
from app.repositories.vector_repository import ChromaVectorRepository
from app.schemas.rag import IndexedChunk, RetrievalFilter
from app.services.embedding_service import HashEmbeddingProvider


def test_chroma_keyword_search_filters_acl_metadata_and_preserves_image(tmp_path):
    vector = ChromaVectorRepository.persistent(tmp_path / "chroma", "hybrid",
                                               HashEmbeddingProvider(dimensions=64))
    vector.upsert_chunks([
        IndexedChunk(chunk_id="PUBLIC", document_id="DOC", document_version_id="PUBLIC-V1",
            content="现代桥梁", source_name="bridge.xlsx", modality="image",
            extraction_method="vision", image_id="img_" + "c" * 64,
            image_index=1, mime_type="image/png", sheet="Sheet1", cell_range="C67:N88"),
        IndexedChunk(chunk_id="SECRET", document_id="SECRET", document_version_id="SECRET-V1",
            content="MAPLE-9063", source_name="secret.xlsx", sheet="Sheet1"),
        IndexedChunk(chunk_id="OTHER", document_id="DOC", document_version_id="PUBLIC-V1",
            content="MAPLE-9063", source_name="other.xlsx", sheet="Other"),
    ])
    keyword = ChromaKeywordRepository(vector)
    result = keyword.search("Sheet1 C67:N88", frozenset({"PUBLIC-V1"}), 5,
                            RetrievalFilter(sheets=frozenset({"Sheet1"})))
    assert [item.chunk_id for item in result] == ["PUBLIC"]
    assert result[0].image_id == "img_" + "c" * 64
    assert result[0].cell_range == "C67:N88"
