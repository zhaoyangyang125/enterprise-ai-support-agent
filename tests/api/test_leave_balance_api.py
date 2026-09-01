from collections.abc import Iterator

from fastapi.testclient import TestClient
import pytest

from app.auth.context import CurrentUser
from app.dependencies import get_leave_service
from app.main import app
from app.schemas.leave_balance import LeaveBalanceResponse
from app.services.errors import LeaveBalanceNotFoundError


class FakeLeaveService:
    """为 API 测试提供固定响应并记录收到的用户。 / Provides a fixed response and records the received user for API tests."""

    def __init__(self, response: LeaveBalanceResponse) -> None:
        """保存预设 API 响应并初始化用户记录。 / Stores the preset API response and initializes user tracking."""

        self._response = response
        self.received_current_user: CurrentUser | None = None

    def get_my_leave_balance(
        self,
        current_user: CurrentUser,
    ) -> LeaveBalanceResponse:
        """记录 API 传入的当前用户并返回预设响应。 / Records the current user passed by the API and returns the preset response."""

        self.received_current_user = current_user
        return self._response


class MissingLeaveBalanceService:
    """记录当前用户并模拟余额记录不存在。 / Records the current user and simulates a missing balance record."""

    def __init__(self) -> None:
        """初始化当前用户调用记录。 / Initializes current-user call tracking."""

        self.received_current_user: CurrentUser | None = None

    def get_my_leave_balance(
        self,
        current_user: CurrentUser,
    ) -> LeaveBalanceResponse:
        """记录当前用户并抛出余额不存在异常。 / Records the current user and raises the missing-balance error."""

        self.received_current_user = current_user
        raise LeaveBalanceNotFoundError()


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    """在每个 API 测试后清除依赖替换。 / Clears dependency overrides after every API test."""

    try:
        yield
    finally:
        app.dependency_overrides.clear()


def test_get_my_leave_balance_returns_200() -> None:
    """验证年假余额 API 返回 200、正确 JSON 和当前用户。 / Verifies the API returns 200, the expected JSON, and the current user."""

    expected_response = LeaveBalanceResponse(remaining_days=8.0)
    fake_service = FakeLeaveService(response=expected_response)

    def override_get_leave_service() -> FakeLeaveService:
        """在当前测试中用 FakeLeaveService 替代真实 Service。 / Replaces the real service with FakeLeaveService for this test."""

        return fake_service

    app.dependency_overrides[get_leave_service] = override_get_leave_service

    client = TestClient(app)
    response = client.get(
        "/api/me/leave-balance",
        headers={"X-User-Id": "U001"},
    )
    assert response.status_code == 200

    assert response.json() == {
        "remaining_days": 8.0,
        "unit": "day",
    }

    assert fake_service.received_current_user is not None
    assert fake_service.received_current_user.user_id == "U001"


def test_get_my_leave_balance_returns_404_when_record_is_missing() -> None:
    """验证余额记录不存在时 API 返回安全的 404。 / Verifies that a missing balance record becomes a safe HTTP 404."""

    fake_service = MissingLeaveBalanceService()

    def override_get_leave_service() -> MissingLeaveBalanceService:
        """在当前测试中提供模拟记录不存在的 Service。 / Provides a service that simulates a missing record."""

        return fake_service

    app.dependency_overrides[get_leave_service] = override_get_leave_service

    client = TestClient(app)
    response = client.get(
        "/api/me/leave-balance",
        headers={"X-User-Id": "U001"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Leave balance not found."}
    assert fake_service.received_current_user is not None
    assert fake_service.received_current_user.user_id == "U001"


def test_get_my_leave_balance_requires_authentication_header() -> None:
    """验证缺少开发认证请求头时 API 拒绝请求。 / Verifies that the API rejects a request without the development auth header."""

    client = TestClient(app)
    response = client.get("/api/me/leave-balance")

    assert response.status_code == 422
