import json
from pathlib import Path

from app.document_processing.parsers import ExcelDocumentParser


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = PROJECT_ROOT / "samples" / "fictional_hmi_test_spec.xlsx"
EXPECTED_REGIONS_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "complex_documents"
    / "fictional_hmi_expected_regions.json"
)


def test_complex_excel_parser_matches_the_confirmed_region_contract() -> None:
    """验证复杂 Excel 的区域类型、定位和关键语义。 / Verifies region types, locations, and key semantics for complex Excel."""

    expected = json.loads(EXPECTED_REGIONS_PATH.read_text(encoding="utf-8"))
    blocks = ExcelDocumentParser().parse(SAMPLE_PATH)

    by_location = {
        (block.sheet, block.cell_range, block.content_type): block
        for block in blocks
    }
    for region in expected["expected_regions"]:
        key = (
            region["sheet"],
            region["cell_range"],
            region["content_type"],
        )
        assert key in by_location, region["region_id"]
        block = by_location[key]
        if section := region.get("section"):
            assert block.section == section
        for text in region["must_contain"]:
            assert text in block.content, (region["region_id"], text, block.content)


def test_complex_excel_parser_keeps_distinct_tables_and_merged_data_meaning() -> None:
    """验证同 Sheet 多表不混用 Header，且纵向合并值能够继承。 / Verifies separate tables keep their own headers and vertically merged values are inherited."""

    blocks = ExcelDocumentParser().parse(SAMPLE_PATH)
    normal_table = next(
        block
        for block in blocks
        if block.sheet == "機能仕様" and block.cell_range == "A8:H12"
    )
    error_table = next(
        block
        for block in blocks
        if block.sheet == "機能仕様" and block.cell_range == "A16:H19"
    )

    assert normal_table.content.count("機能ID=HMI-AC-001") == 2
    assert "CAN信号 / 信号名=HMI_AC_REQ" in normal_table.content
    assert "CAN信号名=HMI_COMM_STATE" in error_table.content
    assert "CAN信号 / 信号名" not in error_table.content
