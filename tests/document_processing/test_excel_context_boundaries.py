"""验证表格上下文的来源和关联边界。 / Tests table context boundaries."""

from openpyxl import Workbook
from openpyxl.styles import Border, Side

from app.document_processing.excel_parser import ExcelDocumentParser
from app.schemas.document import ParsedBlock


def test_single_bordered_row_can_be_a_table(tmp_path):
    """三格闭合单行不能被提前当作段落。 / A bordered three-cell row is a table."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["社員", "年度", "残日数"])
    side = Side(style="thin")
    for cell in sheet[1]:
        cell.border = Border(left=side, right=side, top=side, bottom=side)
    path = tmp_path / "single.xlsx"
    workbook.save(path)
    workbook.close()

    blocks = ExcelDocumentParser().parse(path)
    assert len(blocks) == 1
    assert blocks[0].content_type == "table"
    assert "残日数" in blocks[0].content


def test_two_header_rows_use_physical_location_and_preserve_context_source():
    """关联距离包括表头，附加文字保留自己的来源。 / Includes headers in distance and preserves source."""
    caption = ParsedBlock(content="表1：年休", content_type="title",
                          sheet="年休", cell_range="A1:C1", rows="1")
    table = ParsedBlock(content="社員=U001", content_type="table",
                        sheet="年休", cell_range="A2:C5", rows="4:5")
    result = ExcelDocumentParser()._attach_table_context([caption, table])
    assert "表1：年休" in result[1].content
    assert "年休!A1:C1" in result[1].content
    assert result[1].cell_range == "A2:C5"


def test_unrelated_nearby_paragraph_is_not_attached():
    """无关段落即使贴近表格也不关联。 / Does not attach unrelated adjacent prose."""
    paragraph = ParsedBlock(content="明天举行培训。", sheet="S",
                            cell_range="A3:B3", rows="3")
    table = ParsedBlock(content="社員=U001", content_type="table",
                        sheet="S", cell_range="A4:B5", rows="5")
    result = ExcelDocumentParser()._attach_table_context([paragraph, table])
    assert result[1].content == "社員=U001"


def test_next_section_and_horizontal_neighbor_are_not_attached():
    """下一章节与横向错位文字不关联。 / Excludes next sections and sideways text."""
    caption = ParsedBlock(content="表1：其他数据", content_type="title",
                          sheet="S", cell_range="D1:F1", rows="1")
    table = ParsedBlock(content="社員=U001", content_type="table",
                        sheet="S", cell_range="A2:B4", rows="3:4")
    section = ParsedBlock(content="2. 审批流程", content_type="title",
                          sheet="S", cell_range="A5:B5", rows="5")
    result = ExcelDocumentParser()._attach_table_context([caption, table, section])
    assert result[1].content == "社員=U001"
