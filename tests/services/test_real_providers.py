"""真实适配器的离线契约测试。 / Offline tests for real provider adapters."""
import json
import sys
from types import SimpleNamespace

import httpx
import pytest

from app.dependencies import build_document_parser_registry
from app.services.gemini_vision_provider import GeminiVisionProvider, response_schema
from app.services.google_cloud_vision_ocr_provider import GoogleCloudVisionOcrProvider
from app.services.vision_service import VisionContext


@pytest.mark.parametrize("status", [400, 403, 404, 429])
def test_gemini_status_and_safe_diagnostics(tmp_path, caplog, status):
    """状态码保留，Google错误可诊断，密钥不进入日志。 / Keeps status but redacts secrets."""
    picture = tmp_path / "test.png"
    picture.write_bytes(b"fictional")
    def respond(request):
        return httpx.Response(status, json={"error": {
            "message": "Bad responseSchema test-secret api_key=secret2\ncheck schema"}})
    provider = GeminiVisionProvider("test-secret", transport=httpx.MockTransport(respond))
    result = provider.analyze(picture, VisionContext())
    assert result.error_message == f"vision_http_{status}"
    assert f"status={status}" in caplog.text
    assert "Bad responseSchema" in caplog.text
    assert "test-secret" not in caplog.text
    assert "secret2" not in caplog.text


@pytest.mark.parametrize("output,code", [
    ('{"summary":"demo","image_type":"screenshot","extracted_text":"NAVI","confidence":null}', None),
    ("not JSON", "invalid_vision_response"),
    ('{"summary":" ","image_type":"photo"}', "empty_vision_summary"),
    ('{"summary":"x","image_type":"invented"}', "invalid_vision_response"),
    ('{"summary":"x","image_type":"photo","confidence":2}', "invalid_vision_response"),
])
def test_gemini_minimal_wire_schema_and_validation(tmp_path, output, code):
    """厂商Schema简化，本地校验不放宽。 / Uses minimal schema and strict local validation."""
    path = tmp_path / "test.png"
    path.write_bytes(b"demo")
    def respond(request):
        payload = json.loads(request.content)
        config = payload["generationConfig"]
        assert config["responseJsonSchema"] == response_schema()
        assert "responseSchema" not in config
        schema_text = json.dumps(config["responseJsonSchema"])
        for keyword in ('"title"', '"default"', '"anyOf"', '"additionalProperties"'):
            assert keyword not in schema_text
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP",
            "content": {"parts": [{"text": output}]}}]})
    result = GeminiVisionProvider("fake", "gemini-3.5-flash",
        transport=httpx.MockTransport(respond)).analyze(path, VisionContext())
    assert result.error_message == code
    assert result.success == (code is None)


class StubOcrClient:
    """模拟SDK客户端，记录超时与重试配置。 / Simulates the SDK client."""
    def __init__(self, mode):
        self.mode = mode
        self.calls = 0

    def document_text_detection(self, image, timeout, retry):
        """首次可失败，后续页面仍可成功。 / Can fail one page then recover."""
        self.calls += 1
        assert image["content"] == b"fictional"
        assert timeout == 30
        assert retry is None
        if self.mode == "exception" and self.calls == 1:
            raise RuntimeError("PRIVATE_CREDENTIAL")
        text = "OCR OK"
        message = ""
        if self.mode == "empty":
            text = " "
        if self.mode == "error":
            message = "PRIVATE_RESPONSE"
        return SimpleNamespace(error=SimpleNamespace(message=message),
            full_text_annotation=SimpleNamespace(text=text))


@pytest.mark.parametrize("mode,code", [("ok", None), ("empty", "ocr_empty_result"),
    ("error", "ocr_api_error"), ("exception", "ocr_api_exception")])
def test_google_ocr_client(tmp_path, caplog, mode, code):
    """无网络测试OCR成功、空值、异常及下一页恢复。 / Tests OCR outcomes offline."""
    path = tmp_path / "test.png"
    path.write_bytes(b"fictional")
    client = StubOcrClient(mode)
    provider = GoogleCloudVisionOcrProvider(client)
    result = provider.extract_text(path)
    assert result.error_message == code
    assert result.success == (code is None)
    assert "PRIVATE" not in caplog.text
    if mode == "exception":
        assert provider.extract_text(path).text == "OCR OK"


@pytest.mark.parametrize("image_mode,ocr_mode", [("off", "off"), ("vision", "google"),
    ("ocr", "google"), ("ocr", "off"), ("bad", "bad")])
def test_configuration_is_lazy(monkeypatch, image_mode, ocr_mode):
    """组装不创建云客户端，只有显式模式开启。 / Configuration never calls cloud services."""
    monkeypatch.setenv("DOCUMENT_IMAGE_MODE", image_mode)
    monkeypatch.setenv("DOCUMENT_OCR_MODE", ocr_mode)
    monkeypatch.setenv("GEMINI_VISION_MODEL", "override-model")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    registry = build_document_parser_registry()
    if ocr_mode == "google":
        assert isinstance(registry._ocr_provider, GoogleCloudVisionOcrProvider)
        assert registry._ocr_provider._client is None
    else:
        assert registry._ocr_provider is None
    if image_mode == "vision":
        assert registry._vision_provider._model_name == "override-model"
    elif image_mode == "ocr" and ocr_mode == "google":
        assert registry._image_mode == "ocr"
    else:
        assert registry._image_mode == "off"


def test_google_missing_credentials_degrades_without_leak(tmp_path, monkeypatch, caplog):
    """模拟凭据失败，不实际读取凭据。 / Simulates missing ADC without reading credentials."""
    def fail():
        raise RuntimeError("PRIVATE_CREDENTIAL_PATH")

    fake_module = SimpleNamespace(ImageAnnotatorClient=fail)
    monkeypatch.setitem(sys.modules, "google.cloud.vision", fake_module)
    path = tmp_path / "image.png"
    path.write_bytes(b"fictional")
    result = GoogleCloudVisionOcrProvider().extract_text(path)
    assert result.error_message == "ocr_client_configuration_error"
    assert "PRIVATE_CREDENTIAL_PATH" not in caplog.text


def test_gemini_default_model(monkeypatch):
    """未指定环境变量时使用已确认的模型。 / Uses the project default model."""
    monkeypatch.delenv("GEMINI_VISION_MODEL", raising=False)
    assert GeminiVisionProvider()._model_name == "gemini-3.5-flash"


def test_google_missing_sdk_is_safe(tmp_path, monkeypatch):
    """缺可选SDK时返回明确分类。 / Handles an absent optional SDK."""
    monkeypatch.setitem(sys.modules, "google.cloud.vision", None)
    path = tmp_path / "image.png"
    path.write_bytes(b"fictional")
    assert GoogleCloudVisionOcrProvider().extract_text(path).error_message == "ocr_sdk_missing"
