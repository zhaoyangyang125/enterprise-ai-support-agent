"""显式启用才调用Google OCR，仅使用虚构图片。 / Opt-in paid OCR test."""
import os

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.services.google_cloud_vision_ocr_provider import GoogleCloudVisionOcrProvider


@pytest.mark.skipif(os.getenv("RUN_GOOGLE_OCR_LIVE") != "1",
                   reason="Live Google OCR is disabled by default")
def test_live_google_ocr(tmp_path):
    """通过SDK的ADC加载凭据，不读取JSON内容。 / Uses SDK-managed ADC credentials."""
    path = tmp_path / "fictional.png"
    image = Image.new("RGB", (800, 180), "white")
    drawing = ImageDraw.Draw(image)
    drawing.text((20, 40), "FICTIONAL DEMO: NAVIGATION SCREEN\nOCR OK",
                 fill="black", font=ImageFont.load_default(size=24))
    image.save(path)
    result = GoogleCloudVisionOcrProvider().extract_text(path)
    assert result.success, result.error_message
    assert "NAVIGATION" in result.text.upper()
