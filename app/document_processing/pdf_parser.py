import math
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from app.schemas.document import ParsedBlock


_HEADING_PATTERN = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.．]?\s+|第.+[章節])")
_NUMBER_PATTERN = re.compile(r"\d+")
_SPACE_PATTERN = re.compile(r"\s+")


class PdfDocumentParser:
    """解析有文本层的 PDF，并保留页码与章节。 / Parses text-layer PDFs while preserving pages and sections."""

    def __init__(
        self,
        maximum_chunk_characters: int = 1200,
        margin_candidate_lines: int = 2,
        repeated_margin_ratio: float = 0.6,
    ) -> None:
        """设置 Chunk 大小和重复页眉页脚检测范围。 / Configures chunk size and repeated header/footer detection."""

        if maximum_chunk_characters <= 0:
            raise ValueError("maximum_chunk_characters must be positive")
        if margin_candidate_lines <= 0:
            raise ValueError("margin_candidate_lines must be positive")
        if not 0 < repeated_margin_ratio <= 1:
            raise ValueError("repeated_margin_ratio must be within (0, 1]")
        self._maximum_chunk_characters = maximum_chunk_characters
        self._margin_candidate_lines = margin_candidate_lines
        self._repeated_margin_ratio = repeated_margin_ratio

    def parse(self, path: Path) -> list[ParsedBlock]:
        """清理重复页边内容，并按页面、标题和段落生成 Block。 / Removes repeated margins and creates blocks by page, heading, and paragraph."""

        page_lines = [
            self._extract_lines(page.extract_text() or "")
            for page in PdfReader(path).pages
        ]
        repeated_margins = self._repeated_margin_patterns(page_lines)
        blocks: list[ParsedBlock] = []
        for page_number, lines in enumerate(page_lines, start=1):
            cleaned_lines = self._remove_repeated_margins(lines, repeated_margins)
            blocks.extend(self._page_blocks(cleaned_lines, page_number))
        return blocks

    @staticmethod
    def _extract_lines(text: str) -> list[str]:
        """保留非空文本行并清理首尾空白。 / Keeps non-empty text lines and trims surrounding whitespace."""

        return [line.strip() for line in text.splitlines() if line.strip()]

    def _repeated_margin_patterns(
        self,
        page_lines: list[list[str]],
    ) -> frozenset[str]:
        """统计多页顶部和底部重复出现的规范化文本。 / Finds normalized text repeated at page tops or bottoms."""

        if len(page_lines) < 2:
            return frozenset()
        occurrences: Counter[str] = Counter()
        for lines in page_lines:
            candidates = (
                lines[: self._margin_candidate_lines]
                + lines[-self._margin_candidate_lines :]
            )
            occurrences.update({self._normalize_margin(line) for line in candidates})
        minimum_pages = max(
            2,
            math.ceil(len(page_lines) * self._repeated_margin_ratio),
        )
        return frozenset(
            pattern
            for pattern, count in occurrences.items()
            if pattern and count >= minimum_pages
        )

    def _remove_repeated_margins(
        self,
        lines: list[str],
        repeated_margins: frozenset[str],
    ) -> list[str]:
        """只从页面顶部和底部候选区域移除重复文本。 / Removes repeated text only from top and bottom candidate regions."""

        if not repeated_margins:
            return lines
        last_index = len(lines) - 1
        return [
            line
            for index, line in enumerate(lines)
            if not (
                (
                    index < self._margin_candidate_lines
                    or index > last_index - self._margin_candidate_lines
                )
                and self._normalize_margin(line) in repeated_margins
            )
        ]

    @staticmethod
    def _normalize_margin(line: str) -> str:
        """统一空白并隐藏页码数字，使 Page 1/3 与 Page 2/3 可匹配。 / Normalizes whitespace and masks page numbers for matching."""

        normalized = _SPACE_PATTERN.sub(" ", line).strip().casefold()
        return _NUMBER_PATTERN.sub("#", normalized)

    def _page_blocks(
        self,
        lines: list[str],
        page_number: int,
    ) -> list[ParsedBlock]:
        """将一页内容转换为标题和带 Section 的段落 Block。 / Converts one page into title and section-aware paragraph blocks."""

        blocks: list[ParsedBlock] = []
        paragraph_lines: list[str] = []
        current_section: str | None = None

        def flush_paragraph() -> None:
            nonlocal paragraph_lines
            if not paragraph_lines:
                return
            blocks.extend(
                self._paragraph_blocks(
                    paragraph_lines,
                    page_number,
                    current_section,
                )
            )
            paragraph_lines = []

        for line in lines:
            if _HEADING_PATTERN.match(line):
                flush_paragraph()
                current_section = line
                blocks.append(
                    ParsedBlock(
                        content=line,
                        content_type="title",
                        page=page_number,
                        section=line,
                    )
                )
            else:
                paragraph_lines.append(line)
        flush_paragraph()
        return blocks

    def _paragraph_blocks(
        self,
        lines: list[str],
        page_number: int,
        section: str | None,
    ) -> list[ParsedBlock]:
        """在不跨页的前提下按最大字符数组合段落。 / Groups paragraphs by size without crossing page boundaries."""

        blocks: list[ParsedBlock] = []
        current_parts: list[str] = []
        current_length = 0

        def flush_current() -> None:
            nonlocal current_parts, current_length
            if current_parts:
                blocks.append(
                    ParsedBlock(
                        content="\n".join(current_parts),
                        content_type="paragraph",
                        page=page_number,
                        section=section,
                    )
                )
            current_parts = []
            current_length = 0

        for line in lines:
            for part in self._split_long_line(line):
                separator_length = 1 if current_parts else 0
                projected_length = current_length + separator_length + len(part)
                if current_parts and projected_length > self._maximum_chunk_characters:
                    flush_current()
                current_parts.append(part)
                current_length += (1 if current_length else 0) + len(part)
        flush_current()
        return blocks

    def _split_long_line(self, line: str) -> list[str]:
        """确保单个超长文本行也不会突破 Chunk 上限。 / Ensures an individual long line also respects the chunk limit."""

        return [
            line[index : index + self._maximum_chunk_characters]
            for index in range(0, len(line), self._maximum_chunk_characters)
        ]
