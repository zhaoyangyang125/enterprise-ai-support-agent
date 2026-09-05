from openpyxl import Workbook

from app.document_processing.parsers import ExcelDocumentParser, PdfDocumentParser


def test_excel_parser_preserves_sheet_headers_rows_and_merged_values(tmp_path) -> None:
    """验证 Excel 解析保留 Sheet、Header、Row 和合并单元格语义。 / Verifies Excel parsing preserves sheet, header, row, and merged-cell semantics."""

    path = tmp_path / "travel_policy.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "国内出張"
    sheet.append(["区分", "上限", "備考"])
    sheet.append(["宿泊費", 10000, "1泊"])
    sheet.merge_cells("A3:A4")
    sheet["A3"] = "交通費"
    sheet["B3"] = "実費"
    sheet["B4"] = "領収書必須"
    workbook.save(path)
    workbook.close()

    blocks = ExcelDocumentParser().parse(path)

    assert len(blocks) == 1
    assert blocks[0].content_type == "table"
    assert blocks[0].sheet == "国内出張"
    assert blocks[0].cell_range == "A1:C4"
    assert blocks[0].rows == "2:4"
    assert "区分=宿泊費" in blocks[0].content
    assert "上限=10000" in blocks[0].content
    assert blocks[0].content.count("区分=交通費") == 2


class FakePdfPage:
    """为 PDF Parser 测试提供固定页面文本。 / Provides fixed page text for PDF parser tests."""

    def __init__(self, text: str) -> None:
        """保存页面提取结果。 / Stores the page extraction result."""

        self._text = text

    def extract_text(self) -> str:
        """返回固定文本层内容。 / Returns fixed text-layer content."""

        return self._text


class FakePdfReader:
    """模拟包含两个文本页的 pypdf Reader。 / Simulates a pypdf reader containing two text pages."""

    def __init__(self, _path) -> None:
        """创建固定测试页面。 / Creates fixed test pages."""

        self.pages = [
            FakePdfPage("第一段。\n\n第二段。"),
            FakePdfPage("第三页内容。"),
        ]


def test_pdf_parser_preserves_page_numbers_and_paragraph_chunks(
    monkeypatch,
    tmp_path,
) -> None:
    """验证 PDF Parser 保留页码并按自然段组合 Chunk。 / Verifies the PDF parser preserves page numbers and groups natural paragraphs."""

    monkeypatch.setattr(
        "app.document_processing.pdf_parser.PdfReader",
        FakePdfReader,
    )

    blocks = PdfDocumentParser(maximum_chunk_characters=100).parse(
        tmp_path / "policy.pdf"
    )

    assert [block.page for block in blocks] == [1, 2]
    assert blocks[0].content_type == "paragraph"
    assert blocks[0].content == "第一段。\n第二段。"
    assert blocks[1].content == "第三页内容。"
