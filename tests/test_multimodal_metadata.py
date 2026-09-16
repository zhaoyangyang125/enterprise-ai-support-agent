from pathlib import Path

from app.schemas.document import ParsedBlock
from app.schemas.rag import IndexedChunk, SourceCitation


def test_existing_text_models_keep_backward_compatible_defaults() -> None:
    """验证旧文本代码不传新字段时仍能正常创建模型。 / Verifies old text code still builds models without the new fields."""

    parsed = ParsedBlock(content="普通文本")
    indexed = IndexedChunk(
        chunk_id="TEXT-001",
        document_id="DOC-001",
        document_version_id="DOC-001-V1",
        content="普通文本",
        source_name="policy.pdf",
    )

    assert parsed.modality == "text"
    assert parsed.extraction_method is None
    assert parsed.image_id is None
    assert parsed.image_path is None
    assert indexed.modality == "text"
    assert indexed.image_id is None


def test_image_evidence_models_keep_metadata_but_not_internal_path() -> None:
    """验证内部解析结果可带路径，而对外 Citation 只带安全图片标识。 / Verifies parsing may carry a path while citations expose only safe image identity."""

    parsed = ParsedBlock(
        content="仪表盘警告灯图片",
        content_type="note",
        modality="image",
        extraction_method="vision",
        image_id="IMG-001",
        image_path=Path("internal/images/IMG-001.png"),
        image_index=1,
        mime_type="image/png",
        confidence=0.93,
    )
    citation = SourceCitation(
        document_id="DOC-001",
        document_version_id="DOC-001-V1",
        source_name="manual.pdf",
        location="manual.pdf / Page 2",
        score=0.9,
        modality=parsed.modality,
        extraction_method=parsed.extraction_method,
        image_id=parsed.image_id,
        image_index=parsed.image_index,
        mime_type=parsed.mime_type,
        confidence=parsed.confidence,
    )

    assert parsed.image_path == Path("internal/images/IMG-001.png")
    assert citation.image_id == "IMG-001"
    assert citation.image_url is None
    assert "image_path" not in citation.model_dump()
