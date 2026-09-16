"""把指定 PDF 页面渲染成 OCR 可以读取的 PNG。 / Renders a PDF page as a PNG readable by OCR."""

from pathlib import Path
from typing import Protocol


class RenderedPdfPage:
    """保存渲染后的页面图片 bytes 与 MIME 类型。 / Stores rendered page image bytes and MIME type."""

    def __init__(self, content: bytes, mime_type: str) -> None:
        """接收渲染后的非空图片数据。 / Receives non-empty rendered image data."""

        if not content:
            raise ValueError("Rendered page content must not be empty")
        self.content = content
        self.mime_type = mime_type


class PdfPageRenderer(Protocol):
    """规定 PDF OCR fallback 所需的页面渲染接口。 / Defines the page-rendering interface required by PDF OCR fallback."""

    def render(self, pdf_path: Path, page_index: int) -> RenderedPdfPage:
        """使用从零开始的页序号渲染一页。 / Renders one page using a zero-based page index."""

        ...


class PyMuPdfPageRenderer:
    """使用本地 PyMuPDF 将 PDF 页面渲染为 PNG。 / Uses local PyMuPDF to render PDF pages as PNGs."""

    def __init__(self, zoom: float = 2.0) -> None:
        """设置渲染缩放比例，默认约为 144 DPI。 / Sets the render zoom, approximately 144 DPI by default."""

        if zoom <= 0:
            raise ValueError("zoom must be positive")
        self._zoom = zoom

    def render(self, pdf_path: Path, page_index: int) -> RenderedPdfPage:
        """打开 PDF、渲染指定页并返回 PNG bytes。 / Opens a PDF, renders one page, and returns PNG bytes."""

        # 输入：PDF 路径和从零开始的页序号。
        # 输出：RenderedPdfPage，其中图片格式固定为 PNG。
        # 步骤：打开 PDF -> 检查页号 -> 渲染 -> 关闭 PDF -> 返回 bytes。
        import pymupdf

        document = pymupdf.open(str(pdf_path))
        try:
            if page_index < 0 or page_index >= document.page_count:
                raise IndexError("PDF page index is out of range")

            page = document.load_page(page_index)
            matrix = pymupdf.Matrix(self._zoom, self._zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_content = pixmap.tobytes("png")
        finally:
            document.close()

        return RenderedPdfPage(
            content=image_content,
            mime_type="image/png",
        )
