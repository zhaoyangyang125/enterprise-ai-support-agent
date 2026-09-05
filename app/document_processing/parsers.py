from pathlib import Path
from typing import Protocol

from app.document_processing.excel_parser import ExcelDocumentParser
from app.document_processing.pdf_parser import PdfDocumentParser
from app.schemas.document import ParsedBlock


class DocumentParser(Protocol):
    """定义原始文档转换为带定位语义块的接口。 / Defines the interface for converting an original document into located semantic blocks."""

    def parse(self, path: Path) -> list[ParsedBlock]:
        """解析指定本地文档。 / Parses the specified local document."""

        ...


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
