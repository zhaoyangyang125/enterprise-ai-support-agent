from contextlib import contextmanager
from datetime import date, datetime
from collections.abc import Iterator

import pytest

from app.auth.context import CurrentUser
from app.db.models import LeaveBalance, LeaveRequest, PendingLeaveAction
from app.repositories.leave_request_repository import DuplicateIdempotencyRecordError
from app.services.errors import (
    IdempotencyConflictError,
    InsufficientLeaveBalanceError,
    InvalidLeaveDateRangeError,
)
from app.services.leave_request_service import LeaveRequestService


NOW = datetime(2026, 9, 1, 12, 0, 0)
USER = CurrentUser(user_id="U001")


class FakeLeaveRequestRepository:
    """为安全写入 Service 测试提供可控状态和调用记录。 / Provides controllable state and call tracking for safe-write service tests."""

    def __init__(self, balance: float = 8.0) -> None:
        """初始化余额、待确认操作、申请记录和事务计数。 / Initializes balance, pending actions, requests, and transaction counters."""

        self.balance = LeaveBalance(
            balance_id=1,
            user_id="U001",
            remaining_days=balance,
            updated_at=NOW,
        )
        self.pending_actions: dict[str, PendingLeaveAction] = {}
        self.requests: dict[tuple[str, str], LeaveRequest] = {}
        self.overlap = False
        self.transaction_entries = 0
        self.reserve_calls = 0

    def find_balance(self, user_id: str) -> LeaveBalance | None:
        """返回当前 Fake 余额。 / Returns the current fake balance."""

        return self.balance if user_id == self.balance.user_id else None

    def save_pending_action(self, action: PendingLeaveAction) -> None:
        """保存待确认操作。 / Stores the pending action."""

        self.pending_actions[action.confirmation_token] = action

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """记录确认流程进入了事务边界。 / Records that confirmation entered the transaction boundary."""

        self.transaction_entries += 1
        yield

    def find_request_by_idempotency_key(
        self,
        user_id: str,
        idempotency_key: str,
    ) -> LeaveRequest | None:
        """按用户和幂等键查找 Fake 结果。 / Finds a fake result by user and idempotency key."""

        return self.requests.get((user_id, idempotency_key))

    def find_pending_action_for_update(
        self,
        confirmation_token: str,
    ) -> PendingLeaveAction | None:
        """返回指定待确认操作。 / Returns the specified pending action."""

        return self.pending_actions.get(confirmation_token)

    def has_active_overlap(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> bool:
        """返回预设的日期重叠判断。 / Returns the preset overlap decision."""

        del user_id, start_date, end_date
        return self.overlap

    def reserve_balance(
        self,
        user_id: str,
        days: float,
        updated_at: datetime,
    ) -> bool:
        """模拟条件余额预留并记录扣减次数。 / Simulates conditional balance reservation and records deduction count."""

        if user_id != self.balance.user_id or self.balance.remaining_days < days:
            return False
        self.balance.remaining_days -= days
        self.balance.updated_at = updated_at
        self.reserve_calls += 1
        return True

    def add_request(self, request: LeaveRequest) -> None:
        """保存 Fake 申请结果。 / Stores the fake request result."""

        self.requests[(request.user_id, request.idempotency_key)] = request

    def mark_pending_executed(
        self,
        action: PendingLeaveAction,
        request_id: str,
    ) -> None:
        """把 Fake 待确认操作标记为已执行。 / Marks the fake pending action as executed."""

        action.status = "EXECUTED"
        action.executed_request_id = request_id


def make_service(repository: FakeLeaveRequestRepository) -> LeaveRequestService:
    """创建使用固定时间和编号的 Service。 / Creates a service with fixed time and identifiers."""

    return LeaveRequestService(
        repository=repository,
        clock=lambda: NOW,
        token_factory=lambda: "confirmation-token-001",
        request_id_factory=lambda: "LR-001",
    )


def test_prepare_returns_complete_confirmation_preview() -> None:
    """验证 Prepare 返回确认所需的所有余额和日期信息。 / Verifies prepare returns all date and balance information required for confirmation."""

    repository = FakeLeaveRequestRepository(balance=8.0)
    service = make_service(repository)

    result = service.prepare(USER, date(2026, 9, 7), date(2026, 9, 9))

    assert result.requested_days == 3.0
    assert result.current_balance == 8.0
    assert result.remaining_after_request == 5.0
    assert result.approval_required is False
    assert result.status == "WAITING_CONFIRMATION"
    assert result.confirmation_token in repository.pending_actions


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        (date(2026, 9, 8), date(2026, 9, 7)),
        (date(2026, 9, 5), date(2026, 9, 6)),
    ],
)
def test_prepare_rejects_invalid_or_weekend_only_range(
    start_date: date,
    end_date: date,
) -> None:
    """验证日期倒置或纯周末区间不会生成确认操作。 / Verifies reversed or weekend-only ranges do not create a pending action."""

    repository = FakeLeaveRequestRepository()

    with pytest.raises(InvalidLeaveDateRangeError):
        make_service(repository).prepare(USER, start_date, end_date)

    assert repository.pending_actions == {}


def test_prepare_rejects_insufficient_balance() -> None:
    """验证初次验证余额不足时不生成确认操作。 / Verifies initial insufficient balance does not create a pending action."""

    repository = FakeLeaveRequestRepository(balance=1.0)

    with pytest.raises(InsufficientLeaveBalanceError):
        make_service(repository).prepare(
            USER,
            date(2026, 9, 7),
            date(2026, 9, 9),
        )

    assert repository.pending_actions == {}


def test_confirm_revalidates_changed_balance_before_write() -> None:
    """验证确认后余额变化会在最终再验证时阻止写入。 / Verifies a changed balance blocks the write during final revalidation."""

    repository = FakeLeaveRequestRepository(balance=8.0)
    service = make_service(repository)
    preview = service.prepare(USER, date(2026, 9, 7), date(2026, 9, 9))
    repository.balance.remaining_days = 2.0

    with pytest.raises(InsufficientLeaveBalanceError):
        service.confirm(USER, preview.confirmation_token, True, "idem-key-001")

    assert repository.requests == {}
    assert repository.reserve_calls == 0


def test_confirm_creates_request_and_reserves_balance() -> None:
    """验证明确确认后在事务边界内创建申请并预留余额。 / Verifies explicit confirmation creates a request and reserves balance within a transaction."""

    repository = FakeLeaveRequestRepository(balance=8.0)
    service = make_service(repository)
    preview = service.prepare(USER, date(2026, 9, 7), date(2026, 9, 11))

    result = service.confirm(USER, preview.confirmation_token, True, "idem-key-001")

    assert result.request_id == "LR-001"
    assert result.requested_days == 5.0
    assert result.remaining_after_request == 3.0
    assert result.approval_required is True
    assert result.status == "PENDING_APPROVAL"
    assert repository.balance.remaining_days == 3.0
    assert repository.reserve_calls == 1
    assert repository.transaction_entries == 1


def test_confirm_retry_returns_same_request_without_second_deduction() -> None:
    """验证同一幂等操作重试时返回原结果且余额只扣一次。 / Verifies retrying the same idempotent operation returns the original result and deducts once."""

    repository = FakeLeaveRequestRepository(balance=8.0)
    service = make_service(repository)
    preview = service.prepare(USER, date(2026, 9, 7), date(2026, 9, 9))

    first = service.confirm(USER, preview.confirmation_token, True, "idem-key-001")
    second = service.confirm(USER, preview.confirmation_token, True, "idem-key-001")

    assert second == first
    assert repository.reserve_calls == 1
    assert repository.balance.remaining_days == 5.0


def test_confirm_rejects_same_key_for_different_confirmation() -> None:
    """验证同一幂等键不能复用于另一个确认操作。 / Verifies the same idempotency key cannot be reused for another confirmation."""

    repository = FakeLeaveRequestRepository(balance=8.0)
    service = make_service(repository)
    preview = service.prepare(USER, date(2026, 9, 7), date(2026, 9, 8))
    service.confirm(USER, preview.confirmation_token, True, "idem-key-001")

    with pytest.raises(IdempotencyConflictError):
        service.confirm(USER, "another-confirmation-token", True, "idem-key-001")

    assert repository.reserve_calls == 1


class ConcurrentDuplicateRepository(FakeLeaveRequestRepository):
    """模拟另一事务抢先提交同一幂等操作。 / Simulates another transaction winning the same idempotent operation."""

    def __init__(self) -> None:
        """初始化并发赢家结果占位。 / Initializes the concurrent winner result placeholder."""

        super().__init__(balance=8.0)
        self.concurrent_result: LeaveRequest | None = None

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """模拟失败事务回滚后并发赢家变为可见。 / Simulates the concurrent winner becoming visible after the losing transaction rolls back."""

        original_balance = self.balance.remaining_days
        try:
            yield
        except DuplicateIdempotencyRecordError:
            assert self.concurrent_result is not None
            self.balance.remaining_days = self.concurrent_result.remaining_after_request
            self.requests[
                (
                    self.concurrent_result.user_id,
                    self.concurrent_result.idempotency_key,
                )
            ] = self.concurrent_result
            raise
        else:
            self.balance.remaining_days = original_balance

    def add_request(self, request: LeaveRequest) -> None:
        """保存并发赢家等价结果并触发唯一约束冲突。 / Stores an equivalent winner result and triggers a uniqueness conflict."""

        self.concurrent_result = request
        raise DuplicateIdempotencyRecordError()


def test_confirm_recovers_existing_result_after_concurrent_unique_conflict() -> None:
    """验证并发唯一冲突回滚后重新读取并返回同一结果。 / Verifies a concurrent uniqueness conflict is recovered by rereading the same result after rollback."""

    repository = ConcurrentDuplicateRepository()
    service = make_service(repository)
    preview = service.prepare(USER, date(2026, 9, 7), date(2026, 9, 9))

    result = service.confirm(USER, preview.confirmation_token, True, "idem-key-001")

    assert result.request_id == "LR-001"
    assert result.remaining_after_request == 5.0
    assert repository.balance.remaining_days == 5.0
