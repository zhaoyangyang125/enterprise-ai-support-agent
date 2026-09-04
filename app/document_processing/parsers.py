from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

from app.document_processing.excel_parser import ExcelDocumentParser
from app.schemas.document import ParsedBlock


class DocumentParser(Protocol):
    """定义原始文档转换为带定位语义块的接口。 / Defines the interface for converting an original document into located semantic blocks."""

    def parse(self, path: Path) -> list[ParsedBlock]:
        """解析指定本地文档。 / Parses the specified local document."""

        ...


class PdfDocumentParser:
    """按页和自然段解析带文本层的 PDF。 / Parses text-layer PDFs by page and paragraph."""

    def __init__(self, maximum_chunk_characters: int = 1200) -> None:
        """设置语义段落合并后的最大字符数。 / Sets the maximum size after combining semantic paragraphs."""

        self._maximum_chunk_characters = maximum_chunk_characters

    def parse(self, path: Path) -> list[ParsedBlock]:
        """保留页码并将连续自然段组合成 Chunk。 / Preserves page numbers and groups consecutive paragraphs into chunks."""

        blocks: list[ParsedBlock] = []
        for page_number, page in enumerate(PdfReader(path).pages, start=1):
            text = page.extract_text() or ""
            paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
            current: list[str] = []
            current_length = 0
            for paragraph in paragraphs:
                if current and current_length + len(paragraph) > self._maximum_chunk_characters:
                    blocks.append(
                        ParsedBlock(content="\n\n".join(current), page=page_number)
                    )
                    current = []
                    current_length = 0
                current.append(paragraph)
                current_length += len(paragraph)
            if current:
                blocks.append(ParsedBlock(content="\n\n".join(current), page=page_number))
        return blocks


class DocumentParserRegistry:
    """根据扩展名选择受支持的本地文档解析器。 / Selects a supported local document parser by file extension."""

    def __init__(self) -> None:
        """注册 v1 支持的 PDF 和 Excel 解析器。 / Registers the PDF and Excel parsers supported in v1."""

        excel_parser = ExcelDocumentParser()
        self._parsers: dict[str, DocumentParser] = {
            ".pdf": PdfDocumentParser(),
            ".xlsx": excel_parser,
            ".xlsm": excel_parser,
        }

    def get(self, path: Path) -> DocumentParser:
        """返回对应解析器，不支持的格式会明确失败。 / Returns the matching parser and explicitly fails for unsupported formats."""

        parser = self._parsers.get(path.suffix.casefold())
        if parser is None:
            raise ValueError(f"Unsupported document format: {path.suffix}")
        return parser
