"""图片理解契约与统一内容块转换。 / Vision contract and block conversion."""

from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.document_processing.storage import StoredImageAsset
from app.schemas.document import ParsedBlock


class VisionContext(BaseModel):
    """调用方提供的原文上下文，不由模型生成定位。 / Caller-provided source context."""

    source_name: str | None = None
    sheet: str | None = None
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    nearby_text: str | None = None
    cell_range: str | None = None


class VisionDescription(BaseModel):
    """校验模型生成的内容；置信度不是实测准确率。 / Validates generated descriptions."""

    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1)
    image_type: Literal[
        "screenshot", "flowchart", "architecture_diagram", "table",
        "chart", "photo", "unknown",
    ]
    extracted_text: str = ""
    confidence: float | None = Field(default=None, ge=0, le=1)


class VisionResult(BaseModel):
    """保存图片理解的结果和执行状态。 / Stores description and execution status."""

    success: bool
    provider_name: str
    model_name: str | None = None
    description: VisionDescription | None = None
    error_message: str | None = None


class VisionProvider(Protocol):
    """让业务代码通过统一接口理解图片。 / Defines the replaceable vision interface."""

    def analyze(self, image_path: Path, context: VisionContext) -> VisionResult:
        """输入图片和上下文，返回结构化理解结果。 / Analyzes an image with context."""
        ...


class FakeVisionProvider:
    """返回固定测试结果，不访问网络。 / Returns fixed offline test results."""

    def __init__(self, result: VisionResult) -> None:
        """保存预设结果和调用记录。 / Stores the result and call records."""
        self.result = result
        self.requested_image_paths: list[Path] = []
        self.requested_contexts: list[VisionContext] = []

    def analyze(self, image_path: Path, context: VisionContext) -> VisionResult:
        """记录输入并返回预设结果。 / Records input and returns the preset result."""
        self.requested_image_paths.append(image_path)
        self.requested_contexts.append(context)
        return self.result


class VisionBlockService:
    """将已保存图片转换为现有 ParsedBlock。 / Converts stored images into existing blocks."""

    def __init__(self, provider: VisionProvider) -> None:
        """接收可替换的理解服务。 / Accepts a replaceable provider."""
        self._provider = provider

    def parse(self, asset: StoredImageAsset, context: VisionContext) -> ParsedBlock | None:
        """调用理解服务，失败或空摘要不产生可搜索内容。 / Creates a block only for valid output."""
        result = self._provider.analyze(asset.path, context)
        description = result.description
        if not result.success or description is None:
            return None
        summary = description.summary.strip()
        if not summary:
            return None
        content = summary
        extracted_text = description.extracted_text.strip()
        if extracted_text:
            content += "\n图片文字 / Image text:\n" + extracted_text
        content_type = "paragraph"
        if description.image_type == "table":
            content_type = "table"
        return ParsedBlock(
            content=content, content_type=content_type,
            modality="image", extraction_method="vision",
            image_id=asset.image_id, image_path=asset.path,
            image_index=asset.image_index, mime_type=asset.mime_type,
            confidence=description.confidence, page=context.page,
            sheet=context.sheet, section=context.section,
            cell_range=context.cell_range,
        )
