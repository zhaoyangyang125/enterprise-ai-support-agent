from collections.abc import Iterable
from time import perf_counter
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.repositories.vector_repository import VectorRepository
from app.schemas.rag import RetrievedChunk, RetrievalFilter


class EvaluationClock(Protocol):
    """定义评测计时器接口，便于测试替换。 / Defines the evaluation clock interface for test substitution."""

    def __call__(self) -> float:
        """返回单调递增的时间值。 / Returns a monotonically increasing time value."""

        ...


class ExpectedSourceLocation(BaseModel):
    """定义人工确认的预期来源位置。 / Defines a manually verified expected source location."""

    model_config = ConfigDict(frozen=True)

    source_name: str
    page: int | None = None
    sheet: str | None = None
    cell_range: str | None = None

    def matches(self, chunk: RetrievedChunk) -> bool:
        """检查检索结果是否命中预期的文件和定位信息。 / Checks whether a result matches the expected file and location."""

        return all(
            (
                chunk.source_name == self.source_name,
                self.page is None or chunk.page == self.page,
                self.sheet is None or chunk.sheet == self.sheet,
                self.cell_range is None or chunk.cell_range == self.cell_range,
            )
        )


class RetrievalEvaluationCase(BaseModel):
    """定义一个带权限、过滤条件和人工预期的检索问题。 / Defines one retrieval question with access scope, filters, and human expectations."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    query: str
    allowed_document_version_ids: frozenset[str]
    expects_evidence: bool
    expected_chunk_ids: frozenset[str] = Field(default_factory=frozenset)
    expected_source: ExpectedSourceLocation | None = None
    metadata_filter: RetrievalFilter | None = None


class RetrievalEvaluationItem(BaseModel):
    """记录单个问题的检索结果和判定。 / Records one question's retrieval output and judgment."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    returned_chunk_ids: list[str]
    retrieval_hit: bool | None
    source_hit: bool | None
    no_evidence_correct: bool | None
    retrieval_ms: float
    hit_at_1: bool | None = None
    hit_at_k: bool | None = None
    recall_at_k: float | None = None
    reciprocal_rank: float | None = None


class RetrievalEvaluationReport(BaseModel):
    """汇总小型回归评测指标和逐题结果。 / Summarizes small regression metrics and per-case results."""

    model_config = ConfigDict(frozen=True)

    total_cases: int
    retrieval_hit_rate: float | None
    source_hit_rate: float | None
    no_evidence_accuracy: float | None
    average_retrieval_ms: float
    items: list[RetrievalEvaluationItem]
    hit_at_1: float | None = None
    hit_at_k: float | None = None
    recall_at_k: float | None = None
    mrr: float | None = None


class RetrievalComparisonReport(BaseModel):
    """并列保存Vector-only和Hybrid评测。 / Stores comparable retrieval reports."""

    model_config = ConfigDict(frozen=True)

    vector: RetrievalEvaluationReport
    hybrid: RetrievalEvaluationReport


def evaluate_retrieval(
    repository: VectorRepository,
    cases: list[RetrievalEvaluationCase],
    limit: int = 5,
    clock: EvaluationClock = perf_counter,
) -> RetrievalEvaluationReport:
    """运行确定性的检索回归评测并计算三类指标。 / Runs deterministic retrieval regression evaluation and calculates three metric groups."""

    items: list[RetrievalEvaluationItem] = []
    for case in cases:
        started_at = clock()
        chunks = repository.search(
            query=case.query,
            allowed_document_version_ids=case.allowed_document_version_ids,
            limit=limit,
            metadata_filter=case.metadata_filter,
        )
        elapsed_ms = max(0.0, (clock() - started_at) * 1000)
        returned_ids = [chunk.chunk_id for chunk in chunks]

        if case.expects_evidence:
            if not case.expected_chunk_ids:
                raise ValueError(
                    "Positive evaluation cases must define expected_chunk_ids"
                )
            matching_ids = set(returned_ids) & case.expected_chunk_ids
            retrieval_hit = bool(matching_ids)
            hit_at_1 = bool(returned_ids and returned_ids[0] in case.expected_chunk_ids)
            hit_at_k = retrieval_hit
            recall_at_k = len(matching_ids) / len(case.expected_chunk_ids)
            reciprocal_rank = 0.0
            for rank in range(len(returned_ids)):
                if returned_ids[rank] in case.expected_chunk_ids:
                    reciprocal_rank = 1.0 / (rank + 1)
                    break
            source_hit = (
                None
                if case.expected_source is None
                else any(case.expected_source.matches(chunk) for chunk in chunks)
            )
            no_evidence_correct = None
        else:
            retrieval_hit = None
            hit_at_1 = None
            hit_at_k = None
            recall_at_k = None
            reciprocal_rank = None
            source_hit = None
            no_evidence_correct = not chunks

        items.append(
            RetrievalEvaluationItem(
                case_id=case.case_id,
                returned_chunk_ids=returned_ids,
                retrieval_hit=retrieval_hit,
                source_hit=source_hit,
                no_evidence_correct=no_evidence_correct,
                retrieval_ms=round(elapsed_ms, 3),
                hit_at_1=hit_at_1,
                hit_at_k=hit_at_k,
                recall_at_k=recall_at_k,
                reciprocal_rank=reciprocal_rank,
            )
        )

    return RetrievalEvaluationReport(
        total_cases=len(items),
        retrieval_hit_rate=_optional_rate(
            item.retrieval_hit for item in items
        ),
        source_hit_rate=_optional_rate(item.source_hit for item in items),
        no_evidence_accuracy=_optional_rate(
            item.no_evidence_correct for item in items
        ),
        average_retrieval_ms=(
            round(sum(item.retrieval_ms for item in items) / len(items), 3)
            if items
            else 0.0
        ),
        items=items,
        hit_at_1=_optional_rate(item.hit_at_1 for item in items),
        hit_at_k=_optional_rate(item.hit_at_k for item in items),
        recall_at_k=_optional_average(item.recall_at_k for item in items),
        mrr=_optional_average(item.reciprocal_rank for item in items),
    )


def compare_retrieval(
    vector_repository: VectorRepository,
    hybrid_repository: VectorRepository,
    cases: list[RetrievalEvaluationCase],
    limit: int = 5,
) -> RetrievalComparisonReport:
    """用同一QA Dataset比较两种检索模式。 / Compares two modes on the same dataset."""
    vector_report = evaluate_retrieval(vector_repository, cases, limit)
    hybrid_report = evaluate_retrieval(hybrid_repository, cases, limit)
    return RetrievalComparisonReport(vector=vector_report, hybrid=hybrid_report)


def _optional_rate(values: Iterable[bool | None]) -> float | None:
    """忽略不适用项目并计算布尔结果比例。 / Calculates a boolean rate while ignoring non-applicable items."""

    applicable = [value for value in values if value is not None]
    if not applicable:
        return None
    return round(sum(applicable) / len(applicable), 4)


def _optional_average(values: Iterable[float | None]) -> float | None:
    """忽略不适用项目并计算平均值。 / Averages applicable numeric values."""
    applicable = [value for value in values if value is not None]
    if not applicable:
        return None
    return round(sum(applicable) / len(applicable), 4)
