from pathlib import Path
from types import SimpleNamespace

from scripts.eval_toyota import DEFAULT_CSV, load_questions, rank_of_expected, summarize


def test_question_file_is_well_formed():
    rows = load_questions(DEFAULT_CSV)
    assert len({r["id"] for r in rows}) == len(rows)  # ids are unique
    for r in rows:
        assert r["should_answer"] in ("yes", "no")
        assert (r["should_answer"] == "yes") == bool(r["pages"])  # answerable rows have pages, the others do not


def test_rank_of_expected_uses_the_first_matching_page():
    chunks = [SimpleNamespace(page=5), SimpleNamespace(page=9), SimpleNamespace(page=7)]
    assert rank_of_expected(chunks, {7, 9}) == 2
    assert rank_of_expected(chunks, {1}) is None


def test_summarize_counts_hits_and_refusals():
    results = [
        {"should_answer": "yes", "rank": 1, "evidence": True},
        {"should_answer": "yes", "rank": 4, "evidence": True},
        {"should_answer": "yes", "rank": None, "evidence": False},
        {"should_answer": "no", "rank": None, "evidence": False},
        {"should_answer": "no", "rank": None, "evidence": True},
    ]
    s = summarize(results)
    assert (s["hit@1"], s["hit@3"], s["hit@5"]) == (1, 1, 2)
    assert (s["answered"], s["refused"], s["n_yes"], s["n_no"]) == (2, 1, 3, 2)
