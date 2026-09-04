from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ParsedBlock(BaseModel):
    """表示解析器保留来源定位后的语义内容块。 / Represents a semantic content block with preserved source location."""

    model_config = ConfigDict(frozen=True)

    content: str
    content_type: Literal["title", "key_value", "table", "note", "paragraph"] = (
        "paragraph"
    )
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
