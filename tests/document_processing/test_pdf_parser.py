from pathlib import Path

from app.document_processing.parsers import PdfDocumentParser


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = PROJECT_ROOT / "samples" / "fictional_hmi_policy.pdf"


def test_real_pdf_removes_repeated_margins_and_preserves_page_sections() -> None:
    """验证真实文字型 PDF 清理重复页边内容并保留页码章节。 / Verifies real text PDF margin cleanup and page/section metadata."""

    blocks = PdfDocumentParser().parse(SAMPLE_PATH)
    combined_content = "\n".join(block.content for block in blocks)

    assert {block.page for block in blocks} == {1, 2, 3}
    assert "DEMO-HMI-PDF-001" not in combined_content
    assert "公開可能な完全架空データ" not in combined_content
    assert "Page 1 / 3" not in combined_content
    assert any(
        block.content_type == "title"
        and block.page == 2
        and block.section == "2. 安全制御"
        for block in blocks
    )
    safety_paragraph = next(
        block
        for block in blocks
        if block.content_type == "paragraph" and block.section == "2. 安全制御"
    )
    assert "動画メニューへの画面遷移を禁止" in safety_paragraph.content


class LongLinePdfPage:
    """提供超过 Chunk 上限的固定文本行。 / Provides a fixed text line longer than the chunk limit."""

    def extract_text(self) -> str:
        """返回用于边界测试的文本。 / Returns text for the chunk-boundary test."""

        return "1. Test\nABCDEFGHIJK"


class LongLinePdfReader:
    """模拟单页文字型 PDF Reader。 / Simulates a one-page text PDF reader."""

    def __init__(self, _path) -> None:
        """创建单个测试页面。 / Creates one test page."""

        self.pages = [LongLinePdfPage()]


def test_pdf_parser_splits_a_single_long_line_without_crossing_pages(
    monkeypatch,
    tmp_path,
) -> None:
    """验证单行文本也遵守 Chunk 上限。 / Verifies a single line also respects the chunk limit."""

    monkeypatch.setattr(
        "app.document_processing.pdf_parser.PdfReader",
        LongLinePdfReader,
    )

    blocks = PdfDocumentParser(maximum_chunk_characters=5).parse(
        tmp_path / "long.pdf"
    )

    paragraphs = [block for block in blocks if block.content_type == "paragraph"]
    assert [block.content for block in paragraphs] == ["ABCDE", "FGHIJ", "K"]
    assert all(block.page == 1 for block in paragraphs)
    assert all(block.section == "1. Test" for block in paragraphs)
