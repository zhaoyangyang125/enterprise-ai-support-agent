"""显式启用的真实服务验证，仅上传生成的虚构图片。 / Opt-in live test."""

import os

import pytest
from PIL import Image, ImageDraw

from app.services.gemini_vision_provider import GeminiVisionProvider
from app.services.vision_service import VisionContext


@pytest.mark.skipif(os.getenv("RUN_GEMINI_VISION_LIVE") != "1",
                    reason="Live Gemini calls are disabled by default")
def test_live_gemini_with_fictional_image(tmp_path):
    """人工启用后测试真实API，可能产生费用。 / Explicitly enabled paid API check."""
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_VISION_MODEL")
    if not api_key or not model:
        pytest.skip("Set GEMINI_API_KEY and GEMINI_VISION_MODEL")
    path = tmp_path / "fictional.png"
    image = Image.new("RGB", (400, 150), "white")
    drawing = ImageDraw.Draw(image)
    drawing.text((20, 50), "FICTIONAL DEMO: NAVIGATION SCREEN", fill="black")
    image.save(path)
    provider = GeminiVisionProvider(api_key, model)
    result = provider.analyze(path, VisionContext(source_name="fictional.png"))
    assert result.success, result.error_message
    assert result.description.summary.strip()
