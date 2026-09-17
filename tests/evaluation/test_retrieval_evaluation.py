from app.evaluation.retrieval import (
    RetrievalEvaluationCase,
    evaluate_retrieval,
)
from app.evaluation.sample_suite import run_sample_evaluation, run_sample_comparison
from app.repositories.vector_repository import InMemoryVectorRepository


class FakeClock:
    """提供可预测的评测耗时。 / Provides predictable evaluation timings."""

    def __init__(self) -> None:
        """初始化固定时间序列。 / Initializes a fixed time sequence."""

        self._values = iter((1.0, 1.002, 2.0, 2.006))

    def __call__(self) -> float:
        """依次返回评测开始和结束时间。 / Returns evaluation start and end times in sequence."""

        return next(self._values)


def test_evaluation_calculates_positive_and_no_evidence_metrics() -> None:
    """验证评测分别计算命中率和无答案正确率。 / Verifies evaluation separately calculates hit and no-evidence metrics."""

    report = evaluate_retrieval(
        repository=InMemoryVectorRepository([]),
        cases=[
            RetrievalEvaluationCase(
                case_id="POSITIVE-MISS",
                query="missing",
                allowed_document_version_ids=frozenset({"DOC-V1"}),
                expects_evidence=True,
                expected_chunk_ids=frozenset({"EXPECTED"}),
            ),
            RetrievalEvaluationCase(
                case_id="NO-EVIDENCE-HIT",
                query="none",
                allowed_document_version_ids=frozenset({"DOC-V1"}),
                expects_evidence=False,
            ),
        ],
        clock=FakeClock(),
    )

    assert report.total_cases == 2
    assert report.retrieval_hit_rate == 0.0
    assert report.source_hit_rate is None
    assert report.no_evidence_accuracy == 1.0
    assert report.average_retrieval_ms == 4.0


def test_fictional_hmi_sample_evaluation_passes_all_expectations() -> None:
    """验证六题虚构 HMI 回归评测的检索、来源和无答案结果。 / Verifies retrieval, source, and no-answer results for the six fictional HMI cases."""

    report = run_sample_evaluation()

    assert report.total_cases == 9
    assert report.retrieval_hit_rate == 1.0
    assert report.source_hit_rate == 1.0
    assert report.no_evidence_accuracy == 1.0


def test_evaluation_reports_ranking_metrics_and_mode_comparison() -> None:
    """同一Dataset输出Hit@1/Hit@K/Recall@K/MRR。 / Reports comparable ranking metrics."""
    report = run_sample_comparison()
    for mode in (report.vector, report.hybrid):
        assert mode.total_cases == 9
        assert mode.hit_at_1 is not None
        assert mode.hit_at_k == 1.0
        assert mode.recall_at_k == 1.0
        assert mode.mrr is not None
