from app.evaluation.retrieval import (
    ExpectedSourceLocation,
    RetrievalEvaluationCase,
    RetrievalEvaluationReport,
    evaluate_retrieval,
)
from app.repositories.vector_repository import InMemoryVectorRepository
from app.schemas.rag import IndexedChunk, RetrievalFilter


def run_sample_evaluation() -> RetrievalEvaluationReport:
    """运行六题虚构 HMI 小型回归评测。 / Runs the six-case fictional HMI regression evaluation."""

    repository = InMemoryVectorRepository(_sample_chunks())
    return evaluate_retrieval(repository, _sample_cases())


def _sample_chunks() -> list[IndexedChunk]:
    """创建只包含虚构资料的固定评测索引。 / Creates a fixed evaluation index containing only fictional material."""

    return [
        IndexedChunk(
            chunk_id="PDF-P2-SAFETY",
            document_id="HMI-POLICY",
            document_version_id="HMI-POLICY-V1",
            content="走行中は動画コンテンツ画面への遷移を禁止する。",
            source_name="fictional_hmi_policy.pdf",
            page=2,
            section="2. 安全制御",
        ),
        IndexedChunk(
            chunk_id="PDF-P3-EVIDENCE",
            document_id="HMI-POLICY",
            document_version_id="HMI-POLICY-V1",
            content="根拠資料が不足する場合、システムは規則を推測してはならない。",
            source_name="fictional_hmi_policy.pdf",
            page=3,
            section="3.1 根拠不足時",
        ),
        IndexedChunk(
            chunk_id="XLSX-HMI-AC",
            document_id="HMI-SPEC",
            document_version_id="HMI-SPEC-V1",
            content="機能ID=HMI-AC-001; 期待結果=エアコン画面を表示",
            source_name="fictional_hmi_test_spec.xlsx",
            content_type="table",
            section="1. 基本機能テスト",
            sheet="機能仕様",
            cell_range="A8:H12",
            rows="10:12",
        ),
        IndexedChunk(
            chunk_id="XLSX-CAN-SPEED",
            document_id="HMI-SPEC",
            document_version_id="HMI-SPEC-V1",
            content="車速信号 VehicleSpeed の期待値を確認する。",
            source_name="fictional_hmi_test_spec.xlsx",
            content_type="table",
            section="CAN信号一覧",
            sheet="CAN信号",
            cell_range="A5:F9",
            rows="7:9",
        ),
        IndexedChunk(
            chunk_id="SECRET-CHUNK",
            document_id="SECRET-DOC",
            document_version_id="SECRET-V1",
            content="管理者専用の秘密設定値。",
            source_name="secret_admin_policy.pdf",
            page=1,
        ),
    ]


def _sample_cases() -> list[RetrievalEvaluationCase]:
    """定义人工确认的命中与无答案问题。 / Defines manually verified positive and no-answer cases."""

    return [
        RetrievalEvaluationCase(
            case_id="PDF-001",
            query="走行中の動画画面遷移は許可されますか",
            allowed_document_version_ids=frozenset({"HMI-POLICY-V1"}),
            expects_evidence=True,
            expected_chunk_ids=frozenset({"PDF-P2-SAFETY"}),
            expected_source=ExpectedSourceLocation(
                source_name="fictional_hmi_policy.pdf",
                page=2,
            ),
        ),
        RetrievalEvaluationCase(
            case_id="PDF-002",
            query="根拠が不足する場合に規則を推測してよいですか",
            allowed_document_version_ids=frozenset({"HMI-POLICY-V1"}),
            expects_evidence=True,
            expected_chunk_ids=frozenset({"PDF-P3-EVIDENCE"}),
            expected_source=ExpectedSourceLocation(
                source_name="fictional_hmi_policy.pdf",
                page=3,
            ),
        ),
        RetrievalEvaluationCase(
            case_id="XLSX-001",
            query="HMI-AC-001の期待結果",
            allowed_document_version_ids=frozenset({"HMI-SPEC-V1"}),
            expects_evidence=True,
            expected_chunk_ids=frozenset({"XLSX-HMI-AC"}),
            expected_source=ExpectedSourceLocation(
                source_name="fictional_hmi_test_spec.xlsx",
                sheet="機能仕様",
                cell_range="A8:H12",
            ),
            metadata_filter=RetrievalFilter(
                content_types=frozenset({"table"}),
                sheets=frozenset({"機能仕様"}),
            ),
        ),
        RetrievalEvaluationCase(
            case_id="XLSX-002",
            query="VehicleSpeedの期待値",
            allowed_document_version_ids=frozenset({"HMI-SPEC-V1"}),
            expects_evidence=True,
            expected_chunk_ids=frozenset({"XLSX-CAN-SPEED"}),
            expected_source=ExpectedSourceLocation(
                source_name="fictional_hmi_test_spec.xlsx",
                sheet="CAN信号",
                cell_range="A5:F9",
            ),
            metadata_filter=RetrievalFilter(sheets=frozenset({"CAN信号"})),
        ),
        RetrievalEvaluationCase(
            case_id="SECURITY-001",
            query="管理者専用の秘密設定値",
            allowed_document_version_ids=frozenset({"HMI-POLICY-V1"}),
            expects_evidence=False,
            metadata_filter=RetrievalFilter(
                source_names=frozenset({"secret_admin_policy.pdf"})
            ),
        ),
        RetrievalEvaluationCase(
            case_id="NO-ANSWER-001",
            query="存在しない製品価格規定",
            allowed_document_version_ids=frozenset({"HMI-SPEC-V1"}),
            expects_evidence=False,
            metadata_filter=RetrievalFilter(
                sheets=frozenset({"存在しないSheet"})
            ),
        ),
    ]


if __name__ == "__main__":
    print(run_sample_evaluation().model_dump_json(indent=2))
