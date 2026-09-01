from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth.context import CurrentUser
from app.db.models import Base, LeaveBalance, LeaveRequest, PendingLeaveAction, User
from app.repositories.leave_request_repository import SqlAlchemyLeaveRequestRepository
from app.services.leave_request_service import LeaveRequestService


NOW = datetime(2026, 9, 1, 12, 0, 0)


def make_session() -> Session:
    """创建带固定用户和余额的隔离 Business DB。 / Creates an isolated business database with a fixed user and balance."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    session.add(User(user_id="U001"))
    session.add(
        LeaveBalance(
            user_id="U001",
            remaining_days=8.0,
            updated_at=NOW,
        )
    )
    session.commit()
    return session


def make_service(
    repository: SqlAlchemyLeaveRequestRepository,
) -> LeaveRequestService:
    """创建使用固定时间和编号的真实 Repository Service。 / Creates a real-repository service with fixed time and identifiers."""

    return LeaveRequestService(
        repository=repository,
        clock=lambda: NOW,
        token_factory=lambda: "confirmation-token-001",
        request_id_factory=lambda: "LR-001",
    )


def test_transaction_commits_balance_request_and_pending_state_together() -> None:
    """验证成功事务同时提交余额、申请和确认状态。 / Verifies a successful transaction commits balance, request, and confirmation state together."""

    with make_session() as session:
        repository = SqlAlchemyLeaveRequestRepository(session)
        service = make_service(repository)
        preview = service.prepare(
            CurrentUser(user_id="U001"),
            date(2026, 9, 7),
            date(2026, 9, 9),
        )

        result = service.confirm(
            CurrentUser(user_id="U001"),
            preview.confirmation_token,
            True,
            "idem-key-001",
        )

        balance = session.scalar(
            select(LeaveBalance).where(LeaveBalance.user_id == "U001")
        )
        request = session.get(LeaveRequest, result.request_id)
        pending = session.get(PendingLeaveAction, preview.confirmation_token)

        assert balance is not None and balance.remaining_days == 5.0
        assert request is not None and request.status == "SUBMITTED"
        assert pending is not None and pending.status == "EXECUTED"
        assert pending.executed_request_id == "LR-001"


class FailingLeaveRequestRepository(SqlAlchemyLeaveRequestRepository):
    """在 INSERT 后模拟系统故障以验证事务回滚。 / Simulates a system failure after INSERT to verify transaction rollback."""

    def add_request(self, request: LeaveRequest) -> None:
        """先执行真实 INSERT，再抛出异常。 / Performs the real INSERT and then raises an error."""

        super().add_request(request)
        raise RuntimeError("simulated write failure")


def test_transaction_rolls_back_every_change_when_write_fails() -> None:
    """验证申请写入失败时余额和确认状态均回滚。 / Verifies balance and confirmation state both roll back when request writing fails."""

    with make_session() as session:
        normal_service = make_service(SqlAlchemyLeaveRequestRepository(session))
        preview = normal_service.prepare(
            CurrentUser(user_id="U001"),
            date(2026, 9, 7),
            date(2026, 9, 9),
        )
        failing_service = make_service(FailingLeaveRequestRepository(session))

        with pytest.raises(RuntimeError, match="simulated write failure"):
            failing_service.confirm(
                CurrentUser(user_id="U001"),
                preview.confirmation_token,
                True,
                "idem-key-001",
            )

        balance = session.scalar(
            select(LeaveBalance).where(LeaveBalance.user_id == "U001")
        )
        request = session.get(LeaveRequest, "LR-001")
        pending = session.get(PendingLeaveAction, preview.confirmation_token)

        assert balance is not None and balance.remaining_days == 8.0
        assert request is None
        assert pending is not None and pending.status == "WAITING_CONFIRMATION"
        assert pending.executed_request_id is None
