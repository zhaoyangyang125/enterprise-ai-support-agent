from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


DocumentContentType = Literal["title", "key_value", "table", "note", "paragraph"]


class ParsedBlock(BaseModel):
    """表示解析器保留来源定位后的语义内容块。 / Represents a semantic content block with preserved source location."""

    model_config = ConfigDict(frozen=True)

    content: str
    content_type: DocumentContentType = "paragraph"
    page: int | None = None
    section: str | None = None
    sheet: str | None = None
    cell_range: str | None = None
    rows: str | None = None


class DocumentIngestionResult(BaseModel):
    """定义文档完成解析、存储和索引后的结果。 / Defines the result after document parsing, storage, and indexing."""

    document_id: str
    document_version_id: str
    status: str
    chunk_count: int
    stored_path: Path


class DocumentUploadResponse(BaseModel):
    """定义上传接口可安全返回给界面的处理结果。 / Defines the safe processing result returned by the upload API."""

    document_id: str
    document_version_id: str
    title: str
    status: Literal["active"]
    chunk_count: int


class DocumentVersionStatus(BaseModel):
    """定义文档管理界面显示的版本处理状态。 / Defines the document-version processing state shown in the management UI."""

    document_id: str
    document_version_id: str
    title: str
    version_label: str
    status: Literal["processing", "active", "failed", "inactive"]
