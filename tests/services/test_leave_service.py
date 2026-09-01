from datetime import datetime
import pytest

from app.services.errors import LeaveBalanceNotFoundError
from app.auth.context import CurrentUser
from app.db.models import LeaveBalance
from app.services.leave_service import LeaveService


class FakeLeaveRepository:
    """为 Service 测试提供可控返回值的假 Repository。 / Provides a controllable fake repository for service tests."""

    def __init__(self, result: LeaveBalance | None) -> None:
        """保存预设查询结果并初始化调用记录。 / Stores the preset query result and initializes call tracking."""

        self._result = result
        self.requested_user_id: str | None = None

    def find_by_user_id(self, user_id: str) -> LeaveBalance | None:
        """记录查询的用户编号并返回预设结果。 / Records the queried user ID and returns the preset result."""

        self.requested_user_id = user_id
        return self._result


def test_get_my_leave_balance() -> None:
    """验证 Service 能返回当前用户的正常年假余额。 / Verifies that the service returns the current user's normal leave balance."""

    leave_balance = LeaveBalance(
        balance_id=1,
        user_id="U001",
        remaining_days=8.0,
        updated_at=datetime(2026, 8, 29, 14, 30, 45),
    )

    fake_repository = FakeLeaveRepository(result=leave_balance)

    service = LeaveService(repository=fake_repository)

    current_user = CurrentUser(user_id=leave_balance.user_id)

    result = service.get_my_leave_balance(current_user)
    assert result.remaining_days == 8.0
    assert result.unit == "day"
    assert fake_repository.requested_user_id == "U001"


def test_get_my_leave_balance_raises_when_record_is_missing() -> None:
    """验证余额记录不存在时 Service 抛出业务异常。 / Verifies that the service raises a business error when the record is missing."""

    fake_repository = FakeLeaveRepository(result=None)
    service = LeaveService(repository=fake_repository)
    current_user = CurrentUser(user_id="U001")

    with pytest.raises(LeaveBalanceNotFoundError):
        service.get_my_leave_balance(current_user)

    assert fake_repository.requested_user_id == "U001"


def test_get_my_leave_balance_is_zero() -> None:
    """验证真实余额为零时 Service 正常返回零。 / Verifies that the service normally returns zero for a real zero balance."""

    leave_balance = LeaveBalance(
        balance_id=1,
        user_id="U001",
        remaining_days=0,
        updated_at=datetime(2026, 8, 29, 14, 30, 45),
    )

    fake_repository = FakeLeaveRepository(result=leave_balance)
    service = LeaveService(repository=fake_repository)
    current_user = CurrentUser(user_id=leave_balance.user_id)

    result = service.get_my_leave_balance(current_user)
    assert result.remaining_days == 0
    assert result.unit == "day"
    assert fake_repository.requested_user_id == "U001"
