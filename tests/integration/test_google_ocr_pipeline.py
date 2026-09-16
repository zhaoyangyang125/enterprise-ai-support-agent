"""真实PDF流程加模拟Google客户端，无云调用。 / Real PDF pipeline with a mock SDK client."""
from types import SimpleNamespace

from PIL import Image

from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalImageAssetStorage
from app.services.google_cloud_vision_ocr_provider import GoogleCloudVisionOcrProvider


def test_google_adapter_page_failure_is_isolated(tmp_path):
    """第一页失败不影响第二页OCR与来源定位。 / Isolates page failures."""
    class Client:
        """模拟Google单页失败。 / Simulates one failed page."""
        calls = 0

        def document_text_detection(self, image, timeout, retry):
            """渲染结果必须是PNG，第二页返回文档文字。 / Accepts rendered PNG pages."""
            assert image["content"].startswith(b"\x89PNG")
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("simulated API failure")
            return SimpleNamespace(error=SimpleNamespace(message=""),
                full_text_annotation=SimpleNamespace(text="Fictional navigation document OCR OK"))

    first = Image.new("RGB", (100, 100), "white")
    second = Image.new("RGB", (100, 100), "blue")
    path = tmp_path / "scan.pdf"
    first.save(path, save_all=True, append_images=[second])
    first.close()
    second.close()
    client = Client()
    provider = GoogleCloudVisionOcrProvider(client)
    registry = DocumentParserRegistry(image_storage=LocalImageAssetStorage(tmp_path / "storage"),
                                      ocr_provider=provider)
    blocks = registry.parse_document(path, "DOC", "VER", "scan.pdf")
    assert client.calls == 2
    assert len(blocks) == 1
    assert blocks[0].page == 2
    assert blocks[0].extraction_method == "ocr"
    assert blocks[0].image_id
