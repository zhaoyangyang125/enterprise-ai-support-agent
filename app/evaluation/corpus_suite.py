"""Run a reproducible evaluation against the real fictional document corpus."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.context import CurrentUser
from app.db.models import Base
from app.document_processing.parsers import DocumentParserRegistry
from app.document_processing.storage import LocalDocumentStorage, LocalImageAssetStorage
from app.evaluation.retrieval import ExpectedSourceLocation, RetrievalEvaluationCase, compare_retrieval
from app.repositories.document_access_repository import SqlAlchemyDocumentAccessRepository
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.repositories.hybrid_repository import ChromaKeywordRepository, HybridVectorRepository
from app.repositories.vector_repository import ChromaVectorRepository
from app.schemas.rag import IndexedChunk, RetrievedChunk
from app.services.authorization_service import AuthorizationService
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingProvider, HashEmbeddingProvider
from app.services.ocr_service import FakeOcrProvider, OcrResult
from app.services.rag_service import AnswerGenerator, EvidenceOnlyAnswerGenerator, RagService
from app.services.vision_service import VisionDescription, VisionResult


@dataclass(frozen=True)
class CorpusDocument:
    """Describe one real sample file and its isolated evaluation IDs."""

    file_name: str
    document_id: str
    version_id: str
    title: str


@dataclass(frozen=True)
class CorpusExpectation:
    """Describe a manually verified question and expected source."""

    case_id: str
    query: str
    source_name: str
    required_text: tuple[str, ...]
    page: int | None = None
    sheet: str | None = None
    cell_range: str | None = None
    modality: str | None = None


DOCUMENTS = (
    CorpusDocument("fictional_hmi_policy.pdf", "HMI-POLICY", "HMI-POLICY-V1", "HMI Policy"),
    CorpusDocument("fictional_hmi_test_spec.xlsx", "HMI-SPEC", "HMI-SPEC-V1", "HMI Test Spec"),
    CorpusDocument("fictional_can_diagnostics_reference.pdf", "CAN-DIAG", "CAN-DIAG-V1", "CAN Diagnostics"),
    CorpusDocument("fictional_hmi_change_review.xlsx", "HMI-CHANGE", "HMI-CHANGE-V1", "HMI Change Review"),
    CorpusDocument("fictional_ocr_display_notice.pdf", "OCR-NOTICE", "OCR-NOTICE-V1", "OCR Display Notice"),
)


POSITIVE_EXPECTATIONS = (
    CorpusExpectation("POLICY-001", "対象となるHMI製品は何ですか", "fictional_hmi_policy.pdf", ("Demo Cockpit HMI",), page=1),
    CorpusExpectation("POLICY-002", "走行中に動画メニューを開けますか", "fictional_hmi_policy.pdf", ("動画メニュー", "走行中は操作できません"), page=2),
    CorpusExpectation("POLICY-003", "VEHICLE_SPEEDを10km/hにした時の確認内容", "fictional_hmi_policy.pdf", ("VEHICLE_SPEED", "10km/h"), page=2),
    CorpusExpectation("POLICY-004", "CAN通信断を検出した場合の表示", "fictional_hmi_policy.pdf", ("CAN通信断", "通信確認メッセージ"), page=3),
    CorpusExpectation("POLICY-005", "根拠が不足する場合に会社ルールを推測してよいですか", "fictional_hmi_policy.pdf", ("十分な根拠", "推測して回答しません"), page=3),
    CorpusExpectation("SPEC-001", "HMI-AC-001の期待結果", "fictional_hmi_test_spec.xlsx", ("HMI-AC-001", "エアコン設定画面"), sheet="機能仕様", cell_range="A8:H12"),
    CorpusExpectation("SPEC-002", "HMI-AC-ERR-001でCAN通信断になった場合", "fictional_hmi_test_spec.xlsx", ("HMI-AC-ERR-001", "通信を確認してください"), sheet="機能仕様", cell_range="A16:H19"),
    CorpusExpectation("SPEC-003", "POP-001の発生条件と文言", "fictional_hmi_test_spec.xlsx", ("POP-001", "走行中は操作できません"), sheet="画面遷移", cell_range="A18:F21"),
    CorpusExpectation("SPEC-004", "TR-003でNAVを押した時の遷移先", "fictional_hmi_test_spec.xlsx", ("TR-003", "ナビゲーション"), sheet="画面遷移", cell_range="A10:F14"),
    CorpusExpectation("SPEC-005", "VEHICLE_SPEEDのCAN ID 180h", "fictional_hmi_test_spec.xlsx", ("VEHICLE_SPEED", "180h"), sheet="CAN信号", cell_range="A5:G11"),
    CorpusExpectation("SPEC-006", "GNSS_VALIDが01hの時のHMI動作", "fictional_hmi_test_spec.xlsx", ("GNSS_VALID", "現在地と地図を表示"), sheet="CAN信号", cell_range="A14:D18"),
    CorpusExpectation("CAN-001", "HVAC_TARGET_TEMPのCAN IDは何ですか", "fictional_can_diagnostics_reference.pdf", ("HVAC_TARGET_TEMP", "0x18F"), page=1),
    CorpusExpectation("CAN-002", "DTV_EWS_STATUSのCAN IDは何ですか", "fictional_can_diagnostics_reference.pdf", ("DTV_EWS_STATUS", "0x2A4"), page=1),
    CorpusExpectation("CAN-003", "DTC-HMI-204のフェイルセーフ動作", "fictional_can_diagnostics_reference.pdf", ("DTC-HMI-204", "前回値を維持"), page=2),
    CorpusExpectation("CAN-004", "DTC-HMI-311で許可されない操作", "fictional_can_diagnostics_reference.pdf", ("DTC-HMI-311", "走行中操作を許可しない"), page=2),
    CorpusExpectation("CAN-005", "DTC-DTV-7392受信時に保存するもの", "fictional_can_diagnostics_reference.pdf", ("DTC-DTV-7392", "通常画面の状態を保存"), page=2),
    CorpusExpectation("CHANGE-001", "CHG-DTV-002の期待結果", "fictional_hmi_change_review.xlsx", ("CHG-DTV-002", "操作制限Popup"), sheet="変更一覧", cell_range="A4:F7"),
    CorpusExpectation("CHANGE-002", "DTV EWS通知受信時にNAV画面はどうなりますか", "fictional_hmi_change_review.xlsx", ("DTV EWS通知", "NAV画面を維持"), sheet="画像レビュー", cell_range="A4:B6"),
    CorpusExpectation("CHANGE-003", "画像内のDISP-7392は何を示しますか", "fictional_hmi_change_review.xlsx", ("DISP-7392", "走行中は操作できません"), sheet="画像レビュー", cell_range="B9", modality="image"),
    CorpusExpectation("CHANGE-004", "HVAC_TARGET_TEMPの温度UP操作の期待値", "fictional_hmi_change_review.xlsx", ("HVAC_TARGET_TEMP", "23 ℃"), sheet="CAN確認", cell_range="A4:E7"),
    CorpusExpectation("OCR-001", "DISP-7392の警告内容", "fictional_ocr_display_notice.pdf", ("DISP-7392", "走行中は操作できません"), page=1, modality="image"),
)


class FixedVisionProvider:
    """Return a deterministic description for the fictional embedded image."""

    def analyze(self, path: Path, context: Any) -> VisionResult:
        del path, context
        return VisionResult(
            success=True,
            provider_name="fixed-evaluation",
            description=VisionDescription(
                summary=(
                    "表示メッセージ通知票。警告コード DISP-7392。"
                    "走行中は操作できません。動画メニューへの遷移を抑止する。"
                ),
                image_type="screenshot",
            ),
        )


class CapturingAnswerGenerator:
    """记录每次送给回答器的证据，供确定性 grounding 检查。 / Captures supplied evidence."""

    def __init__(self, delegate: AnswerGenerator) -> None:
        self._delegate = delegate
        self.last_evidence: list[RetrievedChunk] = []

    def generate(self, query: str, evidence: list[RetrievedChunk]) -> str:
        self.last_evidence = list(evidence)
        return self._delegate.generate(query, evidence)


def _fixed_ocr_provider() -> FakeOcrProvider:
    """Return deterministic OCR text for the fictional one-page scan."""

    return FakeOcrProvider(
        OcrResult(
            text=(
                "表示メッセージ通知票\nDISP-7392\n"
                "走行中は操作できません\n"
                "表示制御ユニットは安全制御により動画メニューへの遷移を抑止します。\n"
                "確認対象: DTV EWS受信時の画面状態"
            ),
            confidence=0.99,
            provider_name="fixed-evaluation",
            success=True,
        )
    )


def _matches_expectation(chunk: IndexedChunk, expected: CorpusExpectation) -> bool:
    """Check source metadata and required facts for one golden case."""

    if chunk.source_name != expected.source_name:
        return False
    if expected.page is not None and chunk.page != expected.page:
        return False
    if expected.sheet is not None and chunk.sheet != expected.sheet:
        return False
    if expected.cell_range is not None and chunk.cell_range != expected.cell_range:
        return False
    if expected.modality is not None and chunk.modality != expected.modality:
        return False
    for required_text in expected.required_text:
        if required_text not in chunk.content:
            return False
    return True


def _build_positive_cases(
    chunks: list[IndexedChunk],
    version_ids: frozenset[str],
) -> list[RetrievalEvaluationCase]:
    """Resolve stable chunk IDs from manually verified source facts."""

    cases: list[RetrievalEvaluationCase] = []
    for expected in POSITIVE_EXPECTATIONS:
        matching_ids = frozenset(
            chunk.chunk_id for chunk in chunks if _matches_expectation(chunk, expected)
        )
        if not matching_ids:
            raise AssertionError(f"Golden source was not found: {expected.case_id}")
        cases.append(
            RetrievalEvaluationCase(
                case_id=expected.case_id,
                query=expected.query,
                allowed_document_version_ids=version_ids,
                expects_evidence=True,
                expected_chunk_ids=matching_ids,
                expected_source=ExpectedSourceLocation(
                    source_name=expected.source_name,
                    page=expected.page,
                    sheet=expected.sheet,
                    cell_range=expected.cell_range,
                ),
            )
        )
    return cases


def _report_values(report: Any) -> dict[str, Any]:
    """Return the metrics used in the README and evaluation report."""

    return {
        "total_cases": report.total_cases,
        "hit_at_1": report.hit_at_1,
        "hit_at_k": report.hit_at_k,
        "recall_at_k": report.recall_at_k,
        "mrr": report.mrr,
        "source_hit_rate": report.source_hit_rate,
        "average_retrieval_ms": report.average_retrieval_ms,
        "failed_cases": [
            item.case_id
            for item in report.items
            if item.hit_at_k is False or item.source_hit is False
        ],
    }


def run_corpus_evaluation(
    samples_directory: Path | str = Path("samples"),
    embedding_provider: EmbeddingProvider | None = None,
    answer_generator: AnswerGenerator | None = None,
    minimum_score: float = 0.25,
) -> dict[str, Any]:
    """Ingest five real files and evaluate retrieval, refusal, ACL, and citations."""

    samples_path = Path(samples_directory)
    selected_embedding = embedding_provider or HashEmbeddingProvider()
    selected_answer = answer_generator or EvidenceOnlyAnswerGenerator()
    with TemporaryDirectory(ignore_cleanup_errors=True) as temporary_directory:
        temp = Path(temporary_directory)
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        vector = ChromaVectorRepository.persistent(
            path=temp / "chroma",
            collection_name="corpus_evaluation",
            embedding_provider=selected_embedding,
        )
        hybrid = HybridVectorRepository(vector, ChromaKeywordRepository(vector))
        registry = DocumentParserRegistry(
            image_storage=LocalImageAssetStorage(temp / "storage"),
            vision_provider=FixedVisionProvider(),
            ocr_provider=_fixed_ocr_provider(),
            image_mode="vision",
        )
        ingestion_counts: dict[str, int] = {}
        with Session(engine) as session:
            service = DocumentService(
                repository=SqlAlchemyDocumentRepository(session),
                storage=LocalDocumentStorage(temp / "storage"),
                parser_registry=registry,
                vector_index=vector,
            )
            for document in DOCUMENTS:
                result = service.ingest(
                    source_path=samples_path / document.file_name,
                    document_id=document.document_id,
                    title=document.title,
                    document_version_id=document.version_id,
                    version_label="evaluation-v1",
                    grant_read_to_user_id="U001",
                )
                ingestion_counts[document.file_name] = result.chunk_count

            version_ids = frozenset(document.version_id for document in DOCUMENTS)
            chunks = vector.list_authorized_chunks(version_ids)
            cases = _build_positive_cases(chunks, version_ids)
            comparison = compare_retrieval(vector, hybrid, cases)

            authorization = AuthorizationService(SqlAlchemyDocumentAccessRepository(session))
            capturing_answer = CapturingAnswerGenerator(selected_answer)
            rag_service = RagService(
                authorization,
                hybrid,
                capturing_answer,
                minimum_score=minimum_score,
            )
            authorized_user = CurrentUser(user_id="U001")
            unauthorized_user = CurrentUser(user_id="U999")
            answer_items: list[dict[str, Any]] = []
            for expected in POSITIVE_EXPECTATIONS:
                capturing_answer.last_evidence = []
                answer = rag_service.answer(expected.query, authorized_user)
                source_hit = False
                for source in answer.sources:
                    if source.source_name != expected.source_name:
                        continue
                    if expected.page is not None and source.page != expected.page:
                        continue
                    if expected.sheet is not None and source.sheet != expected.sheet:
                        continue
                    if expected.cell_range is not None and source.cell_range != expected.cell_range:
                        continue
                    source_hit = True
                    break
                fact_in_answer = False
                fact_in_supplied_evidence = False
                for value in expected.required_text:
                    if value in answer.answer:
                        fact_in_answer = True
                    for supplied_chunk in capturing_answer.last_evidence:
                        if value in supplied_chunk.content:
                            fact_in_supplied_evidence = True
                answer_items.append(
                    {
                        "case_id": expected.case_id,
                        "evidence_found": answer.evidence_found,
                        "source_hit": source_hit,
                        # 严格字面检查是可复现的基础指标；LLM 同义改写需要人工复核。
                        # Literal fact matching is reproducible but misses paraphrases.
                        "required_fact_in_answer": fact_in_answer,
                        "required_fact_in_supplied_evidence": fact_in_supplied_evidence,
                        "basic_grounded_check": fact_in_answer and fact_in_supplied_evidence,
                    }
                )
            safety_queries = (
                ("NO-ANSWER-001", "会社では月面基地の駐車料金を毎月いくらまで精算できますか？", authorized_user),
                ("NO-ANSWER-002", "社員食堂の朝食補助上限はいくらですか？", authorized_user),
                ("ACL-001", "DTC-DTV-7392受信時の動作", unauthorized_user),
            )
            safety_items: list[dict[str, Any]] = []
            for case_id, query, user in safety_queries:
                allowed_ids = authorization.get_readable_document_version_ids(user)
                retrieved = hybrid.search(query, allowed_ids, 5)
                answer = rag_service.answer(query, user)
                safety_items.append(
                    {
                        "case_id": case_id,
                        "passed": not answer.evidence_found and not answer.sources,
                        "evidence_found": answer.evidence_found,
                        "source_count": len(answer.sources),
                        "answer": answer.answer,
                        "retrieval_signals": [
                            {
                                "source_name": chunk.source_name,
                                "content": chunk.content[:120],
                                "vector_score": chunk.vector_score,
                                "keyword_match_ratio": chunk.keyword_match_ratio,
                            }
                            for chunk in retrieved
                        ],
                    }
                )

        engine.dispose()
        return {
            "dataset": {
                "documents": len(DOCUMENTS),
                "positive_questions": len(POSITIVE_EXPECTATIONS),
                "safety_questions": len(safety_items),
                "total_questions": len(POSITIVE_EXPECTATIONS) + len(safety_items),
                "chunk_count": len(chunks),
                "ingestion_counts": ingestion_counts,
                "provider_scope": "real local parsers and Chroma; deterministic fake OCR/Vision",
                "embedding_mode": getattr(selected_embedding, "index_identity", "local-hash"),
                "answer_mode": type(selected_answer).__name__,
                "minimum_score": minimum_score,
            },
            "vector": _report_values(comparison.vector),
            "hybrid": _report_values(comparison.hybrid),
            "answer_gate": {
                "evidence_found": sum(
                    1 for item in answer_items if item["evidence_found"]
                ),
                "source_hit": sum(1 for item in answer_items if item["source_hit"]),
                "total": len(answer_items),
                "failed_cases": [
                    item["case_id"]
                    for item in answer_items
                    if not item["source_hit"]
                ],
            },
            "answer_quality": {
                "method": "literal fact in answer AND in evidence actually supplied to generator; paraphrases and other claims need manual review",
                "required_fact_hits": sum(
                    1 for item in answer_items if item["required_fact_in_answer"]
                ),
                "total": len(answer_items),
                "basic_grounded_hits": sum(
                    1 for item in answer_items if item["basic_grounded_check"]
                ),
                "failed_cases": [
                    item["case_id"] for item in answer_items
                    if not item["required_fact_in_answer"]
                ],
            },
            "safety": {
                "passed": sum(1 for item in safety_items if item["passed"]),
                "total": len(safety_items),
                "items": safety_items,
            },
        }
