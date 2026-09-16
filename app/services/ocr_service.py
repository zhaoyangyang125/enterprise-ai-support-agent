"""定义可替换的 OCR 接口和离线测试实现。 / Defines a replaceable OCR interface and offline test implementation."""

from pathlib import Path
from typing import Protocol


class OcrResult:
    """表示一次 OCR 调用的文字、置信度和执行状态。 / Represents text, confidence, and status from one OCR call."""

    def __init__(
        self,
        text: str,
        confidence: float | None,
        provider_name: str,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        """保存 OCR 输出；置信度有值时必须在 0 到 1 之间。 / Stores OCR output and validates optional confidence within 0 to 1."""

        if confidence is not None:
            if confidence < 0 or confidence > 1:
                raise ValueError("confidence must be within [0, 1]")

        self.text = text
        self.confidence = confidence
        self.provider_name = provider_name
        self.success = success
        self.error_message = error_message


class OcrProvider(Protocol):
    """规定 Parser 调用 OCR 时依赖的最小接口。 / Defines the minimum OCR interface required by parsers."""

    def extract_text(self, image_path: Path) -> OcrResult:
        """从指定图片中提取文字。 / Extracts text from the specified image."""

        ...


class FakeOcrProvider:
    """为自动化测试返回固定结果，并记录收到的图片路径。 / Returns a fixed result for tests and records requested image paths."""

    def __init__(self, result: OcrResult) -> None:
        """保存测试需要的固定 OCR 结果。 / Stores the fixed OCR result required by a test."""

        self._result = result
        self.requested_image_paths: list[Path] = []

    def extract_text(self, image_path: Path) -> OcrResult:
        """记录调用路径并返回固定结果，不访问网络。 / Records the image path and returns the fixed result without network access."""

        self.requested_image_paths.append(image_path)
        return self._result
