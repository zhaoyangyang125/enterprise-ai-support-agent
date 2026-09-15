import logging
import math
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from app.document_processing.pdf_renderer import PdfPageRenderer
from app.document_processing.storage import LocalImageAssetStorage
from app.schemas.document import ParsedBlock
from app.services.ocr_service import OcrProvider


_HEADING_PATTERN = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.．]?\s+|第.+[章節])")
_NUMBER_PATTERN = re.compile(r"\d+")
_SPACE_PATTERN = re.compile(r"\s+")
_LOGGER = logging.getLogger(__name__)


class _PdfPageContent:
    """保存一页的文字行及其提取来源 metadata。 / Stores page text lines and extraction-source metadata."""

    def __init__(
        self,
        lines: list[str],
        modality: str,
        extraction_method: str,
        image_id: str | None = None,
        image_path: Path | None = None,
        image_index: int | None = None,
        mime_type: str | None = None,
        confidence: float | None = None,
    ) -> None:
        """保存生成 ParsedBlock 时需要的一页数据。 / Stores one page's data required to create ParsedBlocks."""

        self.lines = lines
        self.modality = modality
        self.extraction_method = extraction_method
        self.image_id = image_id
        self.image_path = image_path
        self.image_index = image_index
        self.mime_type = mime_type
        self.confidence = confidence


class PdfDocumentParser:
    """解析有文本层的 PDF，并保留页码与章节。 / Parses text-layer PDFs while preserving pages and sections."""

    def __init__(
        self,
        maximum_chunk_characters: int = 1200,
        margin_candidate_lines: int = 2,
        repeated_margin_ratio: float = 0.6,
        minimum_native_text_characters: int = 20,
        ocr_provider: OcrProvider | None = None,
        page_renderer: PdfPageRenderer | None = None,
        image_storage: LocalImageAssetStorage | None = None,
    ) -> None:
        """设置文字规则，并可选配置扫描页 OCR fallback。 / Configures text rules and optional scanned-page OCR fallback."""

        if maximum_chunk_characters <= 0:
            raise ValueError("maximum_chunk_characters must be positive")
        if margin_candidate_lines <= 0:
            raise ValueError("margin_candidate_lines must be positive")
        if not 0 < repeated_margin_ratio <= 1:
            raise ValueError("repeated_margin_ratio must be within (0, 1]")
        if minimum_native_text_characters <= 0:
            raise ValueError("minimum_native_text_characters must be positive")

        if ocr_provider is None:
            if page_renderer is not None or image_storage is not None:
                raise ValueError("ocr_provider is required for OCR dependencies")
        else:
            if page_renderer is None or image_storage is None:
                raise ValueError("OCR requires page_renderer and image_storage")

        self._maximum_chunk_characters = maximum_chunk_characters
        self._margin_candidate_lines = margin_candidate_lines
        self._repeated_margin_ratio = repeated_margin_ratio
        self._minimum_native_text_characters = minimum_native_text_characters
        self._ocr_provider = ocr_provider
        self._page_renderer = page_renderer
        self._image_storage = image_storage

    def parse(
        self,
        path: Path,
        document_id: str | None = None,
        document_version_id: str | None = None,
    ) -> list[ParsedBlock]:
        """清理重复页边内容，并按页面、标题和段落生成 Block。 / Removes repeated margins and creates blocks by page, heading, and paragraph."""

        # 输入：PDF 路径；启用 OCR 时还需要文档 ID 和版本 ID。
        # 输出：文字层或 OCR 生成的统一 ParsedBlock。
        # 步骤：逐页读取文字 -> 必要时 OCR -> 清理页边 -> 生成 Block。
        reader = PdfReader(path)
        page_contents: list[_PdfPageContent] = []
        page_lines: list[list[str]] = []

        for page_index in range(len(reader.pages)):
            page = reader.pages[page_index]
            native_text = page.extract_text() or ""
            page_content = self._read_page_content(
                path,
                page_index,
                native_text,
                document_id,
                document_version_id,
            )
            page_contents.append(page_content)
            page_lines.append(page_content.lines)

        repeated_margins = self._repeated_margin_patterns(page_lines)
        blocks: list[ParsedBlock] = []

        for page_index in range(len(page_contents)):
            page_content = page_contents[page_index]
            cleaned_lines = self._remove_repeated_margins(
                page_content.lines,
                repeated_margins,
            )
            page_content.lines = cleaned_lines
            page_number = page_index + 1
            page_blocks = self._page_blocks(page_content, page_number)
            blocks.extend(page_blocks)

        return blocks

    def _read_page_content(
        self,
        path: Path,
        page_index: int,
        native_text: str,
        document_id: str | None,
        document_version_id: str | None,
    ) -> _PdfPageContent:
        """优先使用足够的文字层，否则执行可选 OCR fallback。 / Prefers sufficient text-layer content and otherwise runs optional OCR fallback."""

        if not self._should_use_ocr(native_text):
            return _PdfPageContent(
                lines=self._extract_lines(native_text),
                modality="text",
                extraction_method="text_layer",
            )

        if document_id is None or document_version_id is None:
            raise ValueError("document_id and document_version_id are required for OCR")

        try:
            return self._read_page_with_ocr(
                path, page_index, document_id, document_version_id,
            )
        except Exception:
            _LOGGER.warning("pdf_ocr_failed version=%s page=%s",
                            document_version_id, page_index + 1)
            return _PdfPageContent(
                lines=self._extract_lines(native_text),
                modality="text", extraction_method="text_layer",
            )

    def _should_use_ocr(self, native_text: str) -> bool:
        """只在已配置 OCR 且原生文字明显不足时返回 True。 / Returns True only when OCR is configured and native text is clearly insufficient."""

        if self._ocr_provider is None:
            return False

        text_without_spaces = _SPACE_PATTERN.sub("", native_text)
        return len(text_without_spaces) < self._minimum_native_text_characters

    def _read_page_with_ocr(
        self,
        path: Path,
        page_index: int,
        document_id: str,
        document_version_id: str,
    ) -> _PdfPageContent:
        """渲染、保存并 OCR 一张文字不足的 PDF 页面。 / Renders, stores, and OCRs one PDF page with insufficient text."""

        if self._page_renderer is None:
            raise RuntimeError("PDF page renderer is not configured")
        if self._image_storage is None:
            raise RuntimeError("Image storage is not configured")
        if self._ocr_provider is None:
            raise RuntimeError("OCR provider is not configured")

        rendered_page = self._page_renderer.render(path, page_index)
        page_number = page_index + 1
        stored_asset = self._image_storage.store(
            content=rendered_page.content,
            document_id=document_id,
            document_version_id=document_version_id,
            image_index=page_number,
            mime_type=rendered_page.mime_type,
        )
        ocr_result = self._ocr_provider.extract_text(stored_asset.path)

        if not ocr_result.success or not ocr_result.text.strip():
            _LOGGER.warning(
                "OCR failed for document_version_id=%s page=%s provider=%s error=%s",
                document_version_id,
                page_number,
                ocr_result.provider_name,
                ocr_result.error_message,
            )
            return _PdfPageContent(
                lines=[],
                modality="image",
                extraction_method="ocr",
                image_id=stored_asset.image_id,
                image_path=stored_asset.path,
                image_index=stored_asset.image_index,
                mime_type=stored_asset.mime_type,
                confidence=ocr_result.confidence,
            )

        return _PdfPageContent(
            lines=self._extract_lines(ocr_result.text),
            modality="image",
            extraction_method="ocr",
            image_id=stored_asset.image_id,
            image_path=stored_asset.path,
            image_index=stored_asset.image_index,
            mime_type=stored_asset.mime_type,
            confidence=ocr_result.confidence,
        )

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
        page_content: _PdfPageContent,
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
                    page_content,
                )
            )
            paragraph_lines = []

        for line in page_content.lines:
            if _HEADING_PATTERN.match(line):
                flush_paragraph()
                current_section = line
                blocks.append(
                    self._create_block(
                        content=line,
                        content_type="title",
                        page_content=page_content,
                        page_number=page_number,
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
        page_content: _PdfPageContent,
    ) -> list[ParsedBlock]:
        """在不跨页的前提下按最大字符数组合段落。 / Groups paragraphs by size without crossing page boundaries."""

        blocks: list[ParsedBlock] = []
        current_parts: list[str] = []
        current_length = 0

        def flush_current() -> None:
            nonlocal current_parts, current_length
            if current_parts:
                blocks.append(
                    self._create_block(
                        content="\n".join(current_parts),
                        content_type="paragraph",
                        page_content=page_content,
                        page_number=page_number,
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

    @staticmethod
    def _create_block(
        content: str,
        content_type: str,
        page_content: _PdfPageContent,
        page_number: int,
        section: str | None,
    ) -> ParsedBlock:
        """把页面文字和提取来源统一转换成 ParsedBlock。 / Converts page text and extraction-source data into a ParsedBlock."""

        return ParsedBlock(
            content=content,
            content_type=content_type,
            modality=page_content.modality,
            extraction_method=page_content.extraction_method,
            image_id=page_content.image_id,
            image_path=page_content.image_path,
            image_index=page_content.image_index,
            mime_type=page_content.mime_type,
            confidence=page_content.confidence,
            page=page_number,
            section=section,
        )

    def _split_long_line(self, line: str) -> list[str]:
        """确保单个超长文本行也不会突破 Chunk 上限。 / Ensures an individual long line also respects the chunk limit."""

        return [
            line[index : index + self._maximum_chunk_characters]
            for index in range(0, len(line), self._maximum_chunk_characters)
        ]
