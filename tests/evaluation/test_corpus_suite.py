from app.evaluation.corpus_suite import DOCUMENTS, POSITIVE_EXPECTATIONS, run_corpus_evaluation


def test_real_file_corpus_contains_planned_24_cases() -> None:
    """评测集固定为5份文档、21个正例和3个安全用例。 / Keeps the planned corpus size stable."""

    assert len(DOCUMENTS) == 5
    assert len(POSITIVE_EXPECTATIONS) == 21


def test_real_file_corpus_runs_without_cloud_credentials() -> None:
    """真实文件评测使用确定性Provider并验证拒答和ACL。 / Runs real files deterministically and checks safety cases."""

    report = run_corpus_evaluation()

    assert report["dataset"]["total_questions"] == 24
    assert report["dataset"]["chunk_count"] > 0
    assert report["safety"]["passed"] == 3
    assert report["safety"]["total"] == 3
    assert report["answer_quality"]["total"] == 21
    assert report["answer_quality"]["basic_grounded_hits"] == 21
    assert report["dataset"]["embedding_mode"] == "local-hash"
