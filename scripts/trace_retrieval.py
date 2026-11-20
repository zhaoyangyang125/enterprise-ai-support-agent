"""1つの質問について、検索→証拠判定→補足 の各段階の値を表示する(学習・デバッグ用)。
Prints every stage of one question: search results, evidence level, selection, expansion.

Usage (repo root, venv active):
    python -m scripts.trace_retrieval "USBメモリーの音楽を再生したい"
"""
import argparse
import sys

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
from app.services.context_expander import ContextExpander
from app.services.rag_service import EvidenceOnlyAnswerGenerator, RagService


def _fmt(value: float | None) -> str:
    return "  -  " if value is None else f"{value:.3f}"


def _row(chunk, level: int | None = None) -> str:
    head = chunk.content.split("\n", 1)[-1][:42].replace("\n", " ")
    lvl = "" if level is None else f" L{level}"
    return (f"  score={_fmt(chunk.score)} vec={_fmt(chunk.vector_score)} kw={_fmt(chunk.keyword_score)} "
            f"kwratio={_fmt(chunk.keyword_match_ratio)}{lvl} | p.{chunk.page} {chunk.section_no or ''} | {head}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--user", default="U001")
    args = ap.parse_args()

    vector_repo = get_vector_repository()
    hybrid = get_retrieval_repository(vector_repo)
    with SessionFactory() as session:
        auth = AuthorizationService(SqlAlchemyDocumentAccessRepository(session))
        user = CurrentUser(user_id=args.user, department_id="D-SALES")
        allowed = auth.get_readable_document_version_ids(user)
        service = RagService(auth, hybrid, EvidenceOnlyAnswerGenerator(), minimum_score=get_rag_minimum_score(),
                             minimum_keyword_match_ratio=get_rag_minimum_keyword_match_ratio())

        print(f"Q: {args.query}\n")
        print(f"1) readable document versions: {len(allowed)}")
        retrieved = hybrid.search(args.query, allowed, 5)
        print(f"\n2) search returned {len(retrieved)} chunks (score = RRF rank score, not relevance):")
        levels = [service._get_evidence_level(c) for c in retrieved]
        for chunk, level in zip(retrieved, levels):
            print(_row(chunk, level))
        print(f"\n   thresholds: vector>={service._minimum_score}, keyword ratio>={service._minimum_keyword_match_ratio}"
              f" (L1), >={service._exact_keyword_match_ratio} (L2)")

        evidence = service._select_sufficient_evidence(retrieved)
        print(f"\n3) kept only the highest level -> {len(evidence)} evidence chunks"
              + ("  (NO EVIDENCE: the answer would be the 'not found' message)" if not evidence else ""))
        for chunk in evidence:
            print(_row(chunk))
        if evidence:
            extras = ContextExpander(vector_repo).expand(evidence, allowed)
            print(f"\n4) context expansion added {len(extras)} chunks (after the gate, lower score):")
            for chunk in extras:
                print(_row(chunk))


if __name__ == "__main__":
    main()
