from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.dependencies import get_document_service
from app.main import app
from app.schemas.document import (
    DocumentIngestionResult,
    DocumentVersionStatus,
)


class FakeDocumentService:
    """记录上传 API 的输入并返回固定处理结果。 / Records upload API input and returns fixed processing results."""

    def __init__(self) -> None:
        """初始化上传调用和状态结果。 / Initializes upload calls and status results."""

        self.ingest_calls: list[dict[str, object]] = []
        self.statuses = [
            DocumentVersionStatus(
                document_id="HMI-POLICY",
                document_version_id="HMI-POLICY-V1",
                title="HMI 安全方针",
                version_label="v1.0",
                status="active",
            )
        ]

    def ingest(
        self,
        source_path: Path,
        document_id: str,
        title: str,
        document_version_id: str,
        version_label: str,
        source_name: str | None = None,
        grant_read_to_user_id: str | None = None,
    ) -> DocumentIngestionResult:
        """记录临时文件和业务字段，并模拟处理成功。 / Records the temporary file and business fields and simulates success."""

        self.ingest_calls.append(
            {
                "suffix": source_path.suffix,
                "temporary_exists": source_path.exists(),
                "document_id": document_id,
                "title": title,
                "document_version_id": document_version_id,
                "version_label": version_label,
                "source_name": source_name,
                "grant_read_to_user_id": grant_read_to_user_id,
            }
        )
        return DocumentIngestionResult(
            document_id=document_id,
            document_version_id=document_version_id,
            status="active",
            chunk_count=4,
            stored_path=Path("private/document_storage/source.pdf"),
        )

    def list_versions(self, limit: int = 50) -> list[DocumentVersionStatus]:
        """返回固定的界面状态列表。 / Returns a fixed UI status list."""

        del limit
        return self.statuses


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    """在每个文档 API 测试后清除依赖替换。 / Clears dependency overrides after every document API test."""

    try:
        yield
    finally:
        app.dependency_overrides.clear()


def install_fake_service(service: FakeDocumentService) -> None:
    """将真实文档 Service 替换为测试 Fake。 / Replaces the real document service with a test fake."""

    app.dependency_overrides[get_document_service] = lambda: service


def test_admin_upload_returns_safe_result_and_grants_uploader_read() -> None:
    """验证 ADMIN 上传成功、传入本人权限且不返回服务器路径。 / Verifies admin upload succeeds, grants uploader access, and hides server paths."""

    service = FakeDocumentService()
    install_fake_service(service)
    client = TestClient(app)

    response = client.post(
        "/api/admin/documents",
        headers={"X-User-Id": "U001", "X-Role-Ids": "EMPLOYEE,ADMIN"},
        data={
            "document_id": "HMI-POLICY",
            "title": "HMI 安全方针",
            "document_version_id": "HMI-POLICY-V1",
            "version_label": "v1.0",
        },
        files={"file": ("policy.pdf", b"%PDF fictional", "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json() == {
        "document_id": "HMI-POLICY",
        "document_version_id": "HMI-POLICY-V1",
        "title": "HMI 安全方针",
        "status": "active",
        "chunk_count": 4,
    }
    assert service.ingest_calls == [
        {
            "suffix": ".pdf",
            "temporary_exists": True,
            "document_id": "HMI-POLICY",
            "title": "HMI 安全方针",
            "document_version_id": "HMI-POLICY-V1",
            "version_label": "v1.0",
            "source_name": "policy.pdf",
            "grant_read_to_user_id": "U001",
        }
    ]


def test_document_upload_requires_admin_role() -> None:
    """验证普通员工不能调用文档管理接口。 / Verifies a normal employee cannot call the document management API."""

    service = FakeDocumentService()
    install_fake_service(service)
    client = TestClient(app)

    response = client.post(
        "/api/admin/documents",
        headers={"X-User-Id": "U001", "X-Role-Ids": "EMPLOYEE"},
        data={
            "document_id": "HMI-POLICY",
            "title": "HMI 安全方针",
            "document_version_id": "HMI-POLICY-V1",
            "version_label": "v1.0",
        },
        files={"file": ("policy.pdf", b"%PDF fictional", "application/pdf")},
    )

    assert response.status_code == 403
    assert service.ingest_calls == []


def test_document_upload_rejects_unsupported_file_type() -> None:
    """验证上传边界拒绝 PDF/XLSX 之外的文件。 / Verifies the upload boundary rejects files other than PDF/XLSX."""

    service = FakeDocumentService()
    install_fake_service(service)
    client = TestClient(app)

    response = client.post(
        "/api/admin/documents",
        headers={"X-User-Id": "U001", "X-Role-Ids": "ADMIN"},
        data={
            "document_id": "NOTES",
            "title": "Notes",
            "document_version_id": "NOTES-V1",
            "version_label": "v1",
        },
        files={"file": ("notes.txt", b"text", "text/plain")},
    )

    assert response.status_code == 415
    assert service.ingest_calls == []


def test_admin_can_list_document_processing_statuses() -> None:
    """验证管理界面可以读取文档版本状态。 / Verifies the management UI can read document-version states."""

    service = FakeDocumentService()
    install_fake_service(service)
    client = TestClient(app)

    response = client.get(
        "/api/admin/documents",
        headers={"X-User-Id": "U001", "X-Role-Ids": "ADMIN"},
    )

    assert response.status_code == 200
    assert response.json()[0]["status"] == "active"


def test_root_serves_local_demo_workspace() -> None:
    """验证根路径返回本地演示工作界面。 / Verifies the root path serves the local demonstration workspace."""

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "AI Support Agent" in response.text
    assert "文档上传与索引" in response.text
