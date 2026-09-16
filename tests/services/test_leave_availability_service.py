


from datetime import datetime

from app.auth.context import CurrentUser
from app.db.models import LeaveBalance
from practice.services.leave_availability_service import LeaveAvailabilityService
import pytest
from app.services.errors import LeaveBalanceNotFoundError

class FakeLeaveRepository:
    def __init__(self, result: LeaveBalance | None) -> None:
        self._result = result
        self.requested_user_id: str | None = None

    def find_by_user_id(self, user_id: str) -> LeaveBalance | None:
        self.requested_user_id = user_id
        return self._result


def test_get_leave_availability_returns_false_when_balance_is_zero() -> None:
    
    leave_balance = LeaveBalance(
        balance_id=1,
        user_id="U001",
        remaining_days=0,
        updated_at=datetime(2026, 8, 29, 14, 30, 45),
    )

    fake_repository = FakeLeaveRepository(
        leave_balance
    )
    service = LeaveAvailabilityService(fake_repository)
    current_user = CurrentUser(user_id = leave_balance.user_id)
    result = service.get_leave_availability(current_user= current_user )
    assert result.has_available_leave is False
    assert fake_repository.requested_user_id == "U001"

def test_get_leave_availability_returns_true_when_balance_is_positive() -> None:
    
    leave_balance = LeaveBalance(
        balance_id=1,
        user_id="U001",
        remaining_days=8.0,
        updated_at=datetime(2026, 8, 29, 14, 30, 45),
    )

    fake_repository = FakeLeaveRepository(
        leave_balance
    )
    service = LeaveAvailabilityService(fake_repository)
    current_user = CurrentUser(user_id = leave_balance.user_id)
    result = service.get_leave_availability(current_user= current_user )
    assert result.has_available_leave is True
    assert fake_repository.requested_user_id == "U001"

def test_get_leave_availability_raises_when_record_is_missing() -> None:
    """验证余额记录不存在时 Service 抛出业务异常。 / Verifies that the service raises a business error when the record is missing."""

    fake_repository = FakeLeaveRepository(result=None)
    service = LeaveAvailabilityService(repository=fake_repository)
    current_user = CurrentUser(user_id="U001")
    with pytest.raises(LeaveBalanceNotFoundError):
        result = service.get_leave_availability(current_user= current_user)

    assert fake_repository.requested_user_id == "U001"
    
