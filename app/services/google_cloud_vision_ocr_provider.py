"""Google文档OCR适配器，凭据交给官方SDK处理。 / Google document OCR adapter."""
import logging
from pathlib import Path

from app.services.ocr_service import OcrResult

_LOGGER = logging.getLogger(__name__)


class GoogleCloudVisionOcrProvider:
    """延迟创建ADC客户端，支持离线注入。 / Lazily creates an ADC client."""

    def __init__(self, client=None, timeout_seconds: float = 30) -> None:
        """构造时不读取凭据、不联网。 / Does not load credentials on construction."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._client = client
        self._timeout = timeout_seconds

    def _failure(self, code: str) -> OcrResult:
        """保留稳定分类，不泄露凭据和文档内容。 / Returns a safe error category."""
        _LOGGER.warning("google_ocr_failure code=%s", code)
        return OcrResult("", None, "google_cloud_vision", False, code)

    def extract_text(self, image_path: Path) -> OcrResult:
        """以文档OCR读取单页，异常作为结果返回。 / Reads one page with document OCR."""
        try:
            with image_path.open("rb") as source:
                content = source.read(10 * 1024 * 1024 + 1)
            if not content or len(content) > 10 * 1024 * 1024:
                return self._failure("ocr_invalid_image_size")
        except OSError:
            return self._failure("ocr_image_read_error")
        if self._client is None:
            try:
                from google.cloud import vision
            except ImportError:
                return self._failure("ocr_sdk_missing")
            try:
                self._client = vision.ImageAnnotatorClient()
            except Exception:
                return self._failure("ocr_client_configuration_error")
        try:
            # 扫描企业文档需要整页文字结构，优先document而非普通text_detection。
            response = self._client.document_text_detection(
                image={"content": content}, timeout=self._timeout, retry=None)
            if response.error.message:
                return self._failure("ocr_api_error")
            text = response.full_text_annotation.text.strip()
            if not text:
                return self._failure("ocr_empty_result")
            return OcrResult(text, None, "google_cloud_vision", True)
        except Exception:
            # 不上抛单页故障，下一页仍可调用；不记录含敏感内容的SDK异常正文。
            return self._failure("ocr_api_exception")
