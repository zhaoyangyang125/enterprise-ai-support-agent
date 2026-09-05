from pydantic import BaseModel, ConfigDict, Field

from app.schemas.document import DocumentContentType


class IndexedChunk(BaseModel):
    """表示存入向量检索层的文档片段和来源信息。 / Represents an indexed document chunk and its source metadata."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str
    document_version_id: str
    content: str
    source_name: str
    content_type: DocumentContentType = "paragraph"
    page: int | None = None
    section: str | None = None
    sheet: str | None = None
    cell_range: str | None = None
    rows: str | None = None


class RetrievedChunk(IndexedChunk):
    """表示经过权限过滤和相似度排序后的证据片段。 / Represents an authorized evidence chunk ranked by similarity."""

    score: float = Field(ge=0.0, le=1.0)


class SourceCitation(BaseModel):
    """定义由检索 metadata 生成的可追踪来源。 / Defines a traceable source citation built from retrieval metadata."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    document_version_id: str
    source_name: str
    content_type: DocumentContentType = "paragraph"
    page: int | None = None
    section: str | None = None
    sheet: str | None = None
    cell_range: str | None = None
    rows: str | None = None


class RagAnswerResponse(BaseModel):
    """定义有证据回答或无证据拒答的统一结果。 / Defines the unified result for evidence-backed answers or no-evidence refusals."""

    answer: str
    evidence_found: bool
    sources: list[SourceCitation]
