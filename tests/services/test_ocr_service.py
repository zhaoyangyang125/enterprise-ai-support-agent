from pathlib import Path

import pytest

from app.services.ocr_service import FakeOcrProvider, OcrResult


def test_fake_ocr_provider_returns_success_and_records_path() -> None:
    """验证 Fake OCR 成功结果可控，且不会访问网络。 / Verifies successful fake OCR output is controlled and makes no network call."""

    expected = OcrResult(
        text="扫描页面文字",
        confidence=0.94,
        provider_name="fake-ocr",
        success=True,
    )
    provider = FakeOcrProvider(expected)
    image_path = Path("internal/page_001.png")

    result = provider.extract_text(image_path)

    assert result is expected
    assert provider.requested_image_paths == [image_path]


def test_fake_ocr_provider_can_return_failure() -> None:
    """验证 Fake OCR 可以模拟失败而不是抛出网络异常。 / Verifies fake OCR can simulate failure without raising a network error."""

    expected = OcrResult(
        text="",
        confidence=None,
        provider_name="fake-ocr",
        success=False,
        error_message="simulated timeout",
    )
    provider = FakeOcrProvider(expected)

    result = provider.extract_text(Path("internal/page_002.png"))

    assert result.success is False
    assert result.error_message == "simulated timeout"


def test_ocr_result_rejects_invalid_confidence() -> None:
    """验证 OCR 置信度必须在 0 到 1 之间。 / Verifies OCR confidence must be between 0 and 1."""

    with pytest.raises(ValueError, match="confidence"):
        OcrResult("text", 1.2, "fake-ocr", True)
