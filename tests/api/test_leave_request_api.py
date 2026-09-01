from collections.abc import Iterator
from datetime import date, datetime

from fastapi.testclient import TestClient
import pytest

from app.auth.context import CurrentUser
from app.dependencies import get_leave_request_service
from app.main import app
from app.schemas.leave_request import LeaveRequestPreview, LeaveRequestResponse
from app.services.errors import ConfirmationRequiredError


class FakeLeaveRequestService:
    """为写操作 API 测试返回固定结果并记录安全参数。 / Returns fixed results and records security parameters for write API tests."""

    def __init__(self) -> None:
        """初始化 Prepare 和 Confirm 调用记录。 / Initializes prepare and confirm call tracking."""

        self.prepare_call: tuple[CurrentUser, date, date] | None = None
        self.confirm_call: tuple[CurrentUser, str, bool, str] | None = None

    def prepare(
        self,
        current_user: CurrentUser,
        start_date: date,
        end_date: date,
    ) -> LeaveRequestPreview:
        """记录 Prepare 参数并返回固定确认预览。 / Records prepare parameters and returns a fixed confirmation preview."""

        self.prepare_call = (current_user, start_date, end_date)
        return LeaveRequestPreview(
            confirmation_token="confirmation-token-001",
            start_date=start_date,
            end_date=end_date,
            requested_days=3.0,
            current_balance=8.0,
            remaining_after_request=5.0,
            approval_required=False,
            expires_at=datetime(2026, 9, 1, 12, 15, 0),
        )

    def confirm(
        self,
        current_user: CurrentUser,
        confirmation_token: str,
        confirmed: bool,
        idempotency_key: str,
    ) -> LeaveRequestResponse:
        """记录确认参数并返回固定创建结果。 / Records confirmation parameters and returns a fixed creation result."""

        self.confirm_call = (
            current_user,
            confirmation_token,
            confirmed,
            idempotency_key,
        )
        if not confirmed:
            raise ConfirmationRequiredError()
        return LeaveRequestResponse(
            request_id="LR-001",
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 9),
            requested_days=3.0,
            remaining_after_request=5.0,
            approval_required=False,
            status="SUBMITTED",
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    """在每个写操作 API 测试后清除依赖替换。 / Clears dependency overrides after every write API test."""

    try:
        yield
    finally:
        app.dependency_overrides.clear()


def install_fake_service() -> FakeLeaveRequestService:
    """安装并返回当前测试使用的 Fake Service。 / Installs and returns the fake service used by the current test."""

    fake_service = FakeLeaveRequestService()

    def override_service() -> FakeLeaveRequestService:
        """用 Fake 替换真实写操作 Service。 / Replaces the real write service with the fake."""

        return fake_service

    app.dependency_overrides[get_leave_request_service] = override_service
    return fake_service


def test_prepare_returns_confirmation_preview_for_current_user() -> None:
    """验证 Prepare API 使用当前用户并返回完整预览。 / Verifies the prepare API uses the current user and returns a complete preview."""

    fake_service = install_fake_service()
    response = TestClient(app).post(
        "/api/me/leave-requests/prepare",
        headers={"X-User-Id": "U001"},
        json={"start_date": "2026-09-07", "end_date": "2026-09-09"},
    )

    assert response.status_code == 200
    assert response.json()["remaining_after_request"] == 5.0
    assert response.json()["status"] == "WAITING_CONFIRMATION"
    assert fake_service.prepare_call == (
        CurrentUser(user_id="U001"),
        date(2026, 9, 7),
        date(2026, 9, 9),
    )


def test_confirm_forwards_idempotency_key_and_returns_201() -> None:
    """验证最终 API 转发幂等键并仅在成功时返回 201。 / Verifies the final API forwards the idempotency key and returns 201 only on success."""

    fake_service = install_fake_service()
    response = TestClient(app).post(
        "/api/me/leave-requests",
        headers={"X-User-Id": "U001", "Idempotency-Key": "idem-key-001"},
        json={"confirmation_token": "confirmation-token-001", "confirmed": True},
    )

    assert response.status_code == 201
    assert response.json()["request_id"] == "LR-001"
    assert fake_service.confirm_call == (
        CurrentUser(user_id="U001"),
        "confirmation-token-001",
        True,
        "idem-key-001",
    )


def test_confirm_without_explicit_confirmation_returns_400() -> None:
    """验证未明确确认时 API 不返回成功。 / Verifies the API does not return success without explicit confirmation."""

    install_fake_service()
    response = TestClient(app).post(
        "/api/me/leave-requests",
        headers={"X-User-Id": "U001", "Idempotency-Key": "idem-key-001"},
        json={"confirmation_token": "confirmation-token-001", "confirmed": False},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Explicit confirmation is required."}


def test_confirm_requires_idempotency_key() -> None:
    """验证缺少幂等键时请求在进入 Service 前失败。 / Verifies a request without an idempotency key fails before entering the service."""

    fake_service = install_fake_service()
    response = TestClient(app).post(
        "/api/me/leave-requests",
        headers={"X-User-Id": "U001"},
        json={"confirmation_token": "confirmation-token-001", "confirmed": True},
    )

    assert response.status_code == 422
    assert fake_service.confirm_call is None
