"""离线验证 Vision 输出、安全失败与统一 Block。 / Offline vision tests."""

import json
from pathlib import Path

import httpx
import pytest

from app.document_processing.storage import StoredImageAsset
from app.services.gemini_vision_provider import GeminiVisionProvider
from app.services.vision_service import (
    FakeVisionProvider, VisionBlockService, VisionContext, VisionDescription, VisionResult,
)


def test_fake_vision_creates_located_block():
    """位置来自调用方，理解文字回到统一模型。 / Preserves trusted location."""
    description = VisionDescription(summary="车机显示导航画面", image_type="screenshot",
                                    extracted_text="NAVI", confidence=0.8)
    provider = FakeVisionProvider(VisionResult(success=True, provider_name="fake",
                                               description=description))
    asset = StoredImageAsset("img_test", Path("test.png"), 1, "image/png")
    context = VisionContext(sheet="画面", cell_range="B2", section="导航")
    block = VisionBlockService(provider).parse(asset, context)
    assert block.modality == "image"
    assert block.extraction_method == "vision"
    assert block.cell_range == "B2"
    assert block.image_id == "img_test"
    assert "NAVI" in block.content
    assert provider.requested_image_paths == [asset.path]


def test_failed_vision_does_not_create_error_evidence():
    """失败信息不得变成检索正文。 / Failures produce no evidence."""
    provider = FakeVisionProvider(VisionResult(success=False, provider_name="fake",
                                               error_message="private failure"))
    asset = StoredImageAsset("img_test", Path("test.png"), 1, "image/png")
    assert VisionBlockService(provider).parse(asset, VisionContext()) is None


def test_unconfigured_gemini_does_not_access_image():
    """缺配置仍可构造，无需读取图片或联网。 / Missing configuration stays offline."""
    result = GeminiVisionProvider().analyze(Path("missing.png"), VisionContext())
    assert result.error_message == "vision_not_configured"


@pytest.mark.parametrize("mode", ["success", "timeout", "http", "blocked", "invalid", "truncated"])
def test_gemini_rest_adapter_with_mock_transport(tmp_path, mode):
    """验证实际请求结构及常见失败，绝不联网。 / Tests wire format and failures offline."""
    path = tmp_path / "image.png"
    path.write_bytes(b"test-image")

    def respond(request):
        payload = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == "test-key"
        assert "test-key" not in str(request.url)
        assert "responseJsonSchema" in payload["generationConfig"]
        if mode == "timeout":
            raise httpx.ReadTimeout("private details", request=request)
        if mode == "http":
            return httpx.Response(429, text="private response")
        if mode == "blocked":
            return httpx.Response(200, json={"candidates": []})
        output = json.dumps({"summary": "一个表格", "image_type": "table"})
        if mode == "invalid":
            output = "not json"
        finish = "STOP"
        if mode == "truncated":
            finish = "MAX_TOKENS"
        return httpx.Response(200, json={"candidates": [{
            "finishReason": finish, "content": {"parts": [{"text": output}]},
        }]})

    provider = GeminiVisionProvider("test-key", "test-model",
                                    transport=httpx.MockTransport(respond))
    result = provider.analyze(path, VisionContext())
    assert result.success == (mode == "success")
    if result.success:
        assert result.description.image_type == "table"
    else:
        assert "private" not in result.error_message
        assert result.description is None


@pytest.mark.parametrize("confidence", [-1, 2, float("nan")])
def test_vision_rejects_invalid_confidence(confidence):
    """拒绝不合法置信度。 / Rejects invalid confidence."""
    with pytest.raises(ValueError):
        VisionDescription(summary="文字", image_type="photo", confidence=confidence)
