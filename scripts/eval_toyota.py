"""PRIUS 取扱書の検索を、固定の質問リストで評価する。 / Evaluates retrieval on a fixed question list.

Usage (repo root, venv active; the manual must already be imported):
    python -m scripts.eval_toyota
    python -m scripts.eval_toyota --verbose          # per-question detail for the misses
    python -m scripts.eval_toyota --sweep            # try many thresholds on ONE set of searches (one API call per question)
    RAG_MINIMUM_SCORE=0.4 RAG_MINIMUM_KEYWORD_MATCH_RATIO=0.7 python -m scripts.eval_toyota

CSV columns: id, lang, question, expected_pages (PDF page numbers joined by "|"), should_answer, note.
- should_answer=yes: Hit@1/3/5 = an expected page appears among the top-k chunks.
                     "answered" = the evidence gate lets evidence through.
- should_answer=no : "refused" = the evidence gate returns nothing (the correct outcome).
Results are for this small hand-written list only; do not read them as general accuracy.
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

from app.auth.context import CurrentUser
from app.db.session import SessionFactory
from app.dependencies import (
    get_rag_minimum_keyword_match_ratio,
    get_rag_minimum_score,
    get_retrieval_repository,
    get_vector_repository,
)
from app.repositories.document_access_repository import SqlAlchemyDocumentAccessRepository
from app.services.authorization_service import AuthorizationService
from app.services.rag_service import EvidenceOnlyAnswerGenerator, RagService

DEFAULT_CSV = Path("docs/evaluation/toyota_prius_questions.csv")
TOP_K = (1, 3, 5)
SWEEP_VEC = (0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6)
SWEEP_KW = (0.3, 0.5, 0.7)


def load_questions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["pages"] = {int(p) for p in row["expected_pages"].split("|") if p.strip()}
    return rows


def rank_of_expected(chunks, pages: set[int]) -> int | None:
    return next((i for i, c in enumerate(chunks, 1) if c.page in pages), None)


def summarize(results: list[dict]) -> dict:
    yes = [r for r in results if r["should_answer"] == "yes"]
    no = [r for r in results if r["should_answer"] == "no"]
    out = {"n_yes": len(yes), "n_no": len(no)}
    for k in TOP_K:
        out[f"hit@{k}"] = sum(1 for r in yes if r["rank"] is not None and r["rank"] <= k)
    out["answered"] = sum(1 for r in yes if r["evidence"])
    out["refused"] = sum(1 for r in no if not r["evidence"])
    return out


def print_sweep(results: list[dict], auth, hybrid) -> None:
    """同じ検索結果で閾値の組み合わせだけを変えて評価する(追加のAPI呼び出しなし)。
    Re-applies the evidence gate with many thresholds to the same retrieved chunks."""
    print()
    print("threshold sweep (same searches, no extra API calls):")
    print("  vec   kw   | ja answerable passed | ja unanswerable refused | zh answerable passed | zh unanswerable refused")
    for vec in SWEEP_VEC:
        for kw in SWEEP_KW:
            gate = RagService(auth, hybrid, EvidenceOnlyAnswerGenerator(),
                              minimum_score=vec, minimum_keyword_match_ratio=kw)
            cell = defaultdict(lambda: [0, 0])  # (lang, should_answer) -> [correct, total]
            for r in results:
                passed = bool(gate._select_sufficient_evidence(r["retrieved"]))
                key = (r["lang"], r["should_answer"])
                cell[key][1] += 1
                cell[key][0] += int(passed) if r["should_answer"] == "yes" else int(not passed)
            def f(k):
                return f"{cell[k][0]}/{cell[k][1]}"
            print(f"  {vec:<5} {kw:<4} | {f(('ja', 'yes')):>12}         | {f(('ja', 'no')):>14}          | "
                  f"{f(('zh', 'yes')):>12}       | {f(('zh', 'no')):>12}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--user", default="U001")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--sweep", action="store_true", help="evaluate a grid of evidence thresholds on the same search results")
    args = ap.parse_args()

    hybrid = get_retrieval_repository(get_vector_repository())
    results = []
    with SessionFactory() as session:
        auth = AuthorizationService(SqlAlchemyDocumentAccessRepository(session))
        allowed = auth.get_readable_document_version_ids(CurrentUser(user_id=args.user, department_id="D-SALES"))
        service = RagService(
            auth, hybrid, EvidenceOnlyAnswerGenerator(),
            minimum_score=get_rag_minimum_score(),
            minimum_keyword_match_ratio=get_rag_minimum_keyword_match_ratio(),
        )
        for row in load_questions(args.csv):
            retrieved = hybrid.search(row["question"], allowed, 5)
            results.append({**row, "rank": rank_of_expected(retrieved, row["pages"]), "retrieved": retrieved,
                            "evidence": bool(service._select_sufficient_evidence(retrieved)),
                            "top": [(c.page, (c.heading or c.section or "")[:22]) for c in retrieved[:3]]})

    print(f"thresholds: vector>={service._minimum_score}, keyword ratio>={service._minimum_keyword_match_ratio}\n")
    by_lang = defaultdict(list)
    for r in results:
        by_lang[r["lang"]].append(r)
    for lang, rs in by_lang.items():
        s = summarize(rs)
        hits = ", ".join(f"Hit@{k} {s[f'hit@{k}']}/{s['n_yes']}" for k in TOP_K)
        print(f"[{lang}] answerable: {hits}, evidence passed {s['answered']}/{s['n_yes']} | "
              f"unanswerable: refused {s['refused']}/{s['n_no']}")
    if args.sweep:
        print_sweep(results, auth, hybrid)
    if args.verbose:
        print("\nmisses:")
        for r in results:
            if r["should_answer"] == "yes" and (r["rank"] is None or r["rank"] > 1):
                print(f"  {r['id']} rank={r['rank'] or '>5'} expected={sorted(r['pages'])} top={r['top']} | {r['question']}")
            if r["should_answer"] == "no" and r["evidence"]:
                print(f"  {r['id']} NOT refused | {r['question']}")


if __name__ == "__main__":
    main()
