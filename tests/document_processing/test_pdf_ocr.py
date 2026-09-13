from pathlib import Path

from PIL import Image as PillowImage

from app.document_processing.pdf_parser import PdfDocumentParser
from app.document_processing.pdf_renderer import (
    PyMuPdfPageRenderer,
    RenderedPdfPage,
)
from app.document_processing.storage import LocalImageAssetStorage
from app.services.ocr_service import FakeOcrProvider, OcrResult


class FakePdfPage:
    """为 OCR fallback 测试提供可控的 PDF 文字层。 / Provides controllable PDF text-layer content for OCR fallback tests."""

    def __init__(self, text: str) -> None:
        """保存 page.extract_text 应返回的内容。 / Stores content returned by page.extract_text."""

        self._text = text

    def extract_text(self) -> str:
        """返回预设文字层。 / Returns the preset text layer."""

        return self._text


class FakePdfReader:
    """模拟只包含一页的 pypdf Reader。 / Simulates a one-page pypdf reader."""

    page_text = ""

    def __init__(self, _path: Path) -> None:
        """使用类变量中的文字创建测试页面。 / Creates a test page from the class-level text."""

        self.pages = [FakePdfPage(self.page_text)]


class FakePdfPageRenderer:
    """为 Parser 测试返回固定 PNG bytes 并记录渲染调用。 / Returns fixed PNG bytes and records render calls for parser tests."""

    def __init__(self) -> None:
        """初始化渲染调用记录。 / Initializes render-call tracking."""

        self.calls: list[tuple[Path, int]] = []

    def render(self, pdf_path: Path, page_index: int) -> RenderedPdfPage:
        """记录页号并返回固定页面图片。 / Records the page index and returns a fixed page image."""

        self.calls.append((pdf_path, page_index))
        return RenderedPdfPage(b"fake-rendered-page", "image/png")


def make_ocr_parser(
    tmp_path: Path,
    ocr_result: OcrResult,
) -> tuple[PdfDocumentParser, FakePdfPageRenderer, FakeOcrProvider]:
    """组装使用 Fake Renderer 和 Fake OCR 的 PDF Parser。 / Builds a PDF parser with a fake renderer and fake OCR."""

    renderer = FakePdfPageRenderer()
    provider = FakeOcrProvider(ocr_result)
    parser = PdfDocumentParser(
        minimum_native_text_characters=10,
        ocr_provider=provider,
        page_renderer=renderer,
        image_storage=LocalImageAssetStorage(tmp_path / "document_storage"),
    )
    return parser, renderer, provider


def test_scanned_pdf_page_uses_ocr_fallback(monkeypatch, tmp_path: Path) -> None:
    """验证空文字层页面被渲染、保存并转换成 OCR ParsedBlock。 / Verifies an empty text-layer page is rendered, stored, and converted to an OCR ParsedBlock."""

    FakePdfReader.page_text = ""
    monkeypatch.setattr("app.document_processing.pdf_parser.PdfReader", FakePdfReader)
    result = OcrResult("1. 安全规则\n行驶中禁止播放视频。", 0.92, "fake-ocr", True)
    parser, renderer, provider = make_ocr_parser(tmp_path, result)
    pdf_path = tmp_path / "scanned.pdf"

    blocks = parser.parse(pdf_path, "HMI-POLICY", "HMI-POLICY-V1")

    assert renderer.calls == [(pdf_path, 0)]
    assert len(provider.requested_image_paths) == 1
    assert provider.requested_image_paths[0].is_file()
    assert len(blocks) == 2
    assert blocks[0].content_type == "title"
    assert blocks[1].content == "行驶中禁止播放视频。"
    assert blocks[1].page == 1
    assert blocks[1].modality == "image"
    assert blocks[1].extraction_method == "ocr"
    assert blocks[1].image_id is not None
    assert blocks[1].image_path is not None
    assert blocks[1].mime_type == "image/png"
    assert blocks[1].confidence == 0.92


def test_pdf_with_sufficient_text_does_not_call_ocr(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """验证存在足够文字层时不会进行不必要的渲染或 OCR。 / Verifies sufficient native text avoids unnecessary rendering and OCR."""

    FakePdfReader.page_text = "这是足够长的原生PDF文字内容，不需要执行OCR。"
    monkeypatch.setattr("app.document_processing.pdf_parser.PdfReader", FakePdfReader)
    result = OcrResult("不应该使用", 0.9, "fake-ocr", True)
    parser, renderer, provider = make_ocr_parser(tmp_path, result)

    blocks = parser.parse(
        tmp_path / "native.pdf",
        "HMI-POLICY",
        "HMI-POLICY-V1",
    )

    assert renderer.calls == []
    assert provider.requested_image_paths == []
    assert len(blocks) == 1
    assert blocks[0].modality == "text"
    assert blocks[0].extraction_method == "text_layer"
    assert blocks[0].image_id is None


def test_ocr_failure_does_not_raise_parser_exception(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """验证单页 OCR 失败只跳过该页，不直接抛出 Parser 异常。 / Verifies one OCR failure skips that page without raising a parser exception."""

    FakePdfReader.page_text = ""
    monkeypatch.setattr("app.document_processing.pdf_parser.PdfReader", FakePdfReader)
    result = OcrResult("", None, "fake-ocr", False, "simulated timeout")
    parser, renderer, provider = make_ocr_parser(tmp_path, result)

    blocks = parser.parse(
        tmp_path / "failed.pdf",
        "HMI-POLICY",
        "HMI-POLICY-V1",
    )

    assert blocks == []
    assert len(renderer.calls) == 1
    assert len(provider.requested_image_paths) == 1


def test_pymupdf_renderer_converts_image_pdf_page_to_png(tmp_path: Path) -> None:
    """验证真实本地 Renderer 能把扫描型 PDF 页面转换成 PNG bytes。 / Verifies the real local renderer converts an image-only PDF page to PNG bytes."""

    pdf_path = tmp_path / "image_only.pdf"
    source_image = PillowImage.new("RGB", (40, 30), color=(255, 255, 255))
    source_image.save(pdf_path, format="PDF")
    source_image.close()

    rendered = PyMuPdfPageRenderer(zoom=1.0).render(pdf_path, page_index=0)

    assert rendered.mime_type == "image/png"
    assert rendered.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_real_image_only_pdf_reaches_fake_ocr(tmp_path: Path) -> None:
    """验证真实图片型 PDF 会经过真实 Renderer 并调用 Fake OCR。 / Verifies a real image-only PDF passes through the real renderer and reaches fake OCR."""

    pdf_path = tmp_path / "scanned_policy.pdf"
    source_image = PillowImage.new("RGB", (80, 50), color=(240, 240, 240))
    source_image.save(pdf_path, format="PDF")
    source_image.close()

    ocr_result = OcrResult(
        text="扫描页中的公司规定",
        confidence=0.9,
        provider_name="fake-ocr",
        success=True,
    )
    provider = FakeOcrProvider(ocr_result)
    parser = PdfDocumentParser(
        minimum_native_text_characters=10,
        ocr_provider=provider,
        page_renderer=PyMuPdfPageRenderer(zoom=1.0),
        image_storage=LocalImageAssetStorage(tmp_path / "document_storage"),
    )

    blocks = parser.parse(pdf_path, "POLICY", "POLICY-V1")

    assert len(provider.requested_image_paths) == 1
    assert provider.requested_image_paths[0].is_file()
    assert len(blocks) == 1
    assert blocks[0].content == "扫描页中的公司规定"
    assert blocks[0].modality == "image"
    assert blocks[0].extraction_method == "ocr"
