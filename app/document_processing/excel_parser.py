import re
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.cell_range import CellRange
from openpyxl.worksheet.worksheet import Worksheet

from app.schemas.document import ParsedBlock


_EMPTY_VALUES = (None, "")
_NOTE_PREFIXES = ("注意", "備考", "解析上の期待", "注記", "補足")
_SECTION_PATTERN = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.．]?\s+|第.+[章節])")


class _WorksheetLayout:
    """提供不会破坏原 Workbook 的合并单元格读取视图。 / Provides a merged-cell view without mutating the workbook."""

    def __init__(self, worksheet: Worksheet) -> None:
        self.worksheet = worksheet
        self.merged_ranges = [CellRange(str(item)) for item in worksheet.merged_cells.ranges]
        self._merged_values: dict[tuple[int, int], Any] = {}
        for merged_range in self.merged_ranges:
            value = worksheet.cell(
                row=merged_range.min_row,
                column=merged_range.min_col,
            ).value
            for row in range(merged_range.min_row, merged_range.max_row + 1):
                for column in range(
                    merged_range.min_col,
                    merged_range.max_col + 1,
                ):
                    self._merged_values[(row, column)] = value

    def value(self, row: int, column: int) -> Any:
        """读取普通单元格或合并区域左上角的逻辑值。 / Reads a normal cell or the logical top-left value of a merged region."""

        return self._merged_values.get(
            (row, column),
            self.worksheet.cell(row=row, column=column).value,
        )

    def raw_nonempty_cells(self, row: int) -> list[tuple[int, Any]]:
        """返回该行实际保存值的单元格，不复制合并值。 / Returns physically populated cells without duplicating merged values."""

        return [
            (column, self.worksheet.cell(row=row, column=column).value)
            for column in range(1, self.worksheet.max_column + 1)
            if self.worksheet.cell(row=row, column=column).value
            not in _EMPTY_VALUES
        ]

    def merged_range_starting_at(
        self,
        row: int,
        column: int,
    ) -> CellRange | None:
        """查找以指定单元格为左上角的合并区域。 / Finds the merged region starting at the specified cell."""

        return next(
            (
                item
                for item in self.merged_ranges
                if item.min_row == row and item.min_col == column
            ),
            None,
        )


class ExcelDocumentParser:
    """将 Excel 的结构区域转换为可定位的语义 Block。 / Converts structural Excel regions into located semantic blocks."""

    def parse(self, path: Path) -> list[ParsedBlock]:
        """识别多 Sheet 中的标题、Key-Value、表格和备注区域。 / Detects titles, key-value regions, tables, and notes across sheets."""

        workbook = load_workbook(path, data_only=True)
        try:
            blocks: list[ParsedBlock] = []
            for worksheet in workbook.worksheets:
                blocks.extend(self._parse_worksheet(worksheet))
            return blocks
        finally:
            workbook.close()

    def _parse_worksheet(self, worksheet: Worksheet) -> list[ParsedBlock]:
        """按空白行和独立合并标题切分一个 Sheet。 / Splits one sheet by blank rows and standalone merged headings."""

        layout = _WorksheetLayout(worksheet)
        blocks: list[ParsedBlock] = []
        buffered_rows: list[int] = []
        current_section: str | None = None
        row = 1

        while row <= worksheet.max_row:
            standalone = self._standalone_block(
                layout,
                row,
                current_section,
            )
            if standalone is not None:
                blocks.extend(
                    self._convert_region(layout, buffered_rows, current_section)
                )
                buffered_rows = []
                block, ending_row, is_section = standalone
                blocks.append(block)
                if is_section:
                    current_section = block.content
                row = ending_row + 1
                continue

            if self._row_is_empty(layout, row):
                blocks.extend(
                    self._convert_region(layout, buffered_rows, current_section)
                )
                buffered_rows = []
            else:
                buffered_rows.append(row)
            row += 1

        blocks.extend(self._convert_region(layout, buffered_rows, current_section))
        return blocks

    def _standalone_block(
        self,
        layout: _WorksheetLayout,
        row: int,
        current_section: str | None,
    ) -> tuple[ParsedBlock, int, bool] | None:
        """识别占据独立行的标题、章节或备注。 / Detects a standalone title, section, or note."""

        cells = layout.raw_nonempty_cells(row)
        if len(cells) != 1:
            return None

        column, value = cells[0]
        text = self._text(value)
        merged_range = layout.merged_range_starting_at(row, column)
        spans_region = merged_range is not None and (
            merged_range.max_col > merged_range.min_col
            or merged_range.max_row > merged_range.min_row
        )
        is_note = text.startswith(_NOTE_PREFIXES)
        is_section = bool(_SECTION_PATTERN.match(text))
        is_title = spans_region or row <= 2 or is_section
        if not (is_note or is_title):
            return None

        if merged_range is None:
            merged_range = CellRange(
                min_col=column,
                min_row=row,
                max_col=column,
                max_row=row,
            )
        content_type = "note" if is_note else "title"
        block = ParsedBlock(
            content=text,
            content_type=content_type,
            section=current_section if is_note else None,
            sheet=layout.worksheet.title,
            cell_range=str(merged_range),
            rows=self._row_label(merged_range.min_row, merged_range.max_row),
        )
        return block, merged_range.max_row, is_section

    def _convert_region(
        self,
        layout: _WorksheetLayout,
        rows: list[int],
        current_section: str | None,
    ) -> list[ParsedBlock]:
        """把连续非空行转换为 Key-Value、Table 或 Paragraph。 / Converts contiguous populated rows into key-value, table, or paragraph blocks."""

        if not rows:
            return []
        min_column, max_column = self._column_bounds(layout, rows)
        cell_range = self._cell_range(
            min_column,
            rows[0],
            max_column,
            rows[-1],
        )
        if self._looks_like_key_value(layout, rows):
            return [
                ParsedBlock(
                    content=self._key_value_content(layout, rows),
                    content_type="key_value",
                    section=current_section,
                    sheet=layout.worksheet.title,
                    cell_range=cell_range,
                    rows=self._row_label(rows[0], rows[-1]),
                )
            ]
        if len(rows) == 1:
            return [
                ParsedBlock(
                    content=self._paragraph_content(
                        layout,
                        rows[0],
                        min_column,
                        max_column,
                    ),
                    content_type="paragraph",
                    section=current_section,
                    sheet=layout.worksheet.title,
                    cell_range=cell_range,
                    rows=str(rows[0]),
                )
            ]
        header_depth = self._header_depth(
            layout,
            rows,
            min_column,
            max_column,
        )
        data_rows = rows[header_depth:] or rows
        return [
            ParsedBlock(
                content=self._table_content(
                    layout,
                    rows,
                    min_column,
                    max_column,
                ),
                content_type="table",
                section=current_section,
                sheet=layout.worksheet.title,
                cell_range=cell_range,
                rows=self._row_label(data_rows[0], data_rows[-1]),
            )
        ]

    @staticmethod
    def _row_is_empty(layout: _WorksheetLayout, row: int) -> bool:
        """判断一行在合并值展开后是否为空。 / Checks whether a row is empty after logical merged-value expansion."""

        return all(
            layout.value(row, column) in _EMPTY_VALUES
            for column in range(1, layout.worksheet.max_column + 1)
        )

    @staticmethod
    def _column_bounds(
        layout: _WorksheetLayout,
        rows: list[int],
    ) -> tuple[int, int]:
        """计算区域真实使用的最小和最大列。 / Calculates the actual minimum and maximum used columns."""

        columns = [
            column
            for row in rows
            for column in range(1, layout.worksheet.max_column + 1)
            if layout.value(row, column) not in _EMPTY_VALUES
        ]
        return min(columns), max(columns)

    @staticmethod
    def _looks_like_key_value(
        layout: _WorksheetLayout,
        rows: list[int],
    ) -> bool:
        """识别两列或带空列分隔的 Label/Value 配对区域。 / Detects two-column or gap-separated label/value regions."""

        first_row_columns = [
            column for column, _value in layout.raw_nonempty_cells(rows[0])
        ]
        if len(rows) < 3 and len(first_row_columns) == 2:
            return False
        for row in rows:
            columns = [column for column, _value in layout.raw_nonempty_cells(row)]
            if len(columns) < 2 or len(columns) % 2 != 0:
                return False
            pairs = list(zip(columns[::2], columns[1::2], strict=True))
            if any(right != left + 1 for left, right in pairs):
                return False
            if len(pairs) > 1 and not any(
                pairs[index + 1][0] > pairs[index][1] + 1
                for index in range(len(pairs) - 1)
            ):
                return False
        return True

    def _key_value_content(
        self,
        layout: _WorksheetLayout,
        rows: list[int],
    ) -> str:
        """把 Label/Value 配对区域转换为逐行语义文本。 / Converts label/value pairs into row-oriented semantic text."""

        lines: list[str] = []
        for row in rows:
            cells = layout.raw_nonempty_cells(row)
            pairs = [
                f"{self._text(cells[index][1])}={self._text(cells[index + 1][1])}"
                for index in range(0, len(cells), 2)
            ]
            lines.append("; ".join(pairs))
        return "\n".join(lines)

    def _table_content(
        self,
        layout: _WorksheetLayout,
        rows: list[int],
        min_column: int,
        max_column: int,
    ) -> str:
        """组合多行表头，并为每个数据值补充完整 Header 路径。 / Combines multi-row headers and prefixes every value with its full header path."""

        header_depth = self._header_depth(
            layout,
            rows,
            min_column,
            max_column,
        )
        header_rows = rows[:header_depth]
        data_rows = rows[header_depth:]
        headers = [
            self._header_path(layout, header_rows, column, min_column)
            for column in range(min_column, max_column + 1)
        ]
        if not data_rows:
            return "; ".join(headers)

        lines: list[str] = []
        for row in data_rows:
            pairs = [
                f"{headers[column - min_column]}={self._text(value)}"
                for column in range(min_column, max_column + 1)
                if (value := layout.value(row, column)) not in _EMPTY_VALUES
            ]
            if pairs:
                lines.append("; ".join(pairs))
        return "\n".join(lines)

    @staticmethod
    def _header_depth(
        layout: _WorksheetLayout,
        rows: list[int],
        min_column: int,
        max_column: int,
    ) -> int:
        """根据 Header 区域内的纵向或横向合并判断是否为两行表头。 / Detects a two-row header from vertical or horizontal merges."""

        if len(rows) < 3 or rows[1] != rows[0] + 1:
            return 1
        first_row, second_row = rows[0], rows[1]
        for merged_range in layout.merged_ranges:
            intersects_columns = not (
                merged_range.max_col < min_column
                or merged_range.min_col > max_column
            )
            if not intersects_columns or merged_range.min_row != first_row:
                continue
            if merged_range.max_row >= second_row:
                return 2
            if merged_range.max_col > merged_range.min_col and any(
                layout.value(second_row, column) not in _EMPTY_VALUES
                for column in range(
                    merged_range.min_col,
                    merged_range.max_col + 1,
                )
            ):
                return 2
        return 1

    def _header_path(
        self,
        layout: _WorksheetLayout,
        header_rows: list[int],
        column: int,
        first_column: int,
    ) -> str:
        """将父子 Header 去重后组合成稳定路径。 / Combines de-duplicated parent and child headers into a stable path."""

        parts: list[str] = []
        for row in header_rows:
            value = layout.value(row, column)
            if value in _EMPTY_VALUES:
                continue
            text = self._text(value)
            if not parts or parts[-1] != text:
                parts.append(text)
        if parts:
            return " / ".join(parts)
        return f"column_{column - first_column + 1}"

    def _paragraph_content(
        self,
        layout: _WorksheetLayout,
        row: int,
        min_column: int,
        max_column: int,
    ) -> str:
        """把无法分类的单行内容保留为普通段落。 / Preserves an unclassified single row as a paragraph."""

        return "; ".join(
            self._text(value)
            for column in range(min_column, max_column + 1)
            if (value := layout.value(row, column)) not in _EMPTY_VALUES
        )

    @staticmethod
    def _text(value: Any) -> str:
        """统一转换单元格值并清理首尾空白。 / Converts cell values consistently and trims surrounding whitespace."""

        return str(value).strip()

    @staticmethod
    def _cell_range(
        min_column: int,
        min_row: int,
        max_column: int,
        max_row: int,
    ) -> str:
        """把数字边界转换为 Excel A1 Range。 / Converts numeric bounds into an Excel A1 range."""

        return (
            f"{get_column_letter(min_column)}{min_row}:"
            f"{get_column_letter(max_column)}{max_row}"
        )

    @staticmethod
    def _row_label(min_row: int, max_row: int) -> str:
        """保留旧 Citation 使用的行号表示。 / Preserves the legacy row label used by existing citations."""

        return str(min_row) if min_row == max_row else f"{min_row}:{max_row}"
