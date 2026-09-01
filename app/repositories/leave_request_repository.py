from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from typing import ContextManager, Protocol

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import LeaveBalance, LeaveRequest, PendingLeaveAction


class DuplicateIdempotencyRecordError(Exception):
    """表示数据库唯一约束发现并发幂等记录。 / Indicates that a database uniqueness constraint found a concurrent idempotency record."""


class LeaveRequestRepository(Protocol):
    """定义安全年假申请流程所需的数据访问和事务接口。 / Defines data access and transaction operations for safe leave requests."""

    def find_balance(self, user_id: str) -> LeaveBalance | None: ...

    def save_pending_action(self, action: PendingLeaveAction) -> None: ...

    def transaction(self) -> ContextManager[None]: ...

    def find_request_by_idempotency_key(
        self, user_id: str, idempotency_key: str
    ) -> LeaveRequest | None: ...

    def find_pending_action_for_update(
        self, confirmation_token: str
    ) -> PendingLeaveAction | None: ...

    def has_active_overlap(
        self, user_id: str, start_date: date, end_date: date
    ) -> bool: ...

    def reserve_balance(self, user_id: str, days: float, updated_at: datetime) -> bool: ...

    def add_request(self, request: LeaveRequest) -> None: ...

    def mark_pending_executed(
        self, action: PendingLeaveAction, request_id: str
    ) -> None: ...


class SqlAlchemyLeaveRequestRepository:
    """使用 SQLAlchemy 实现年假申请的事务性数据访问。 / Implements transactional leave-request data access with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """保存当前请求使用的数据库会话。 / Stores the database session used by the current request."""

        self._session = session

    def find_balance(self, user_id: str) -> LeaveBalance | None:
        """按用户编号查询当前余额。 / Finds the current balance by user ID."""

        return self._session.scalar(
            select(LeaveBalance).where(LeaveBalance.user_id == user_id)
        )

    def save_pending_action(self, action: PendingLeaveAction) -> None:
        """保存待确认操作并立即提交 Prepare 阶段。 / Saves and commits the pending action during the prepare stage."""

        self._session.add(action)
        self._session.commit()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """保证确认阶段的所有数据库变更一起提交或回滚。 / Ensures all confirmation-stage changes commit or roll back together."""

        with self._session.begin():
            yield

    def find_request_by_idempotency_key(
        self,
        user_id: str,
        idempotency_key: str,
    ) -> LeaveRequest | None:
        """查询同一用户和幂等键已经创建的结果。 / Finds an existing result for the same user and idempotency key."""

        return self._session.scalar(
            select(LeaveRequest).where(
                LeaveRequest.user_id == user_id,
                LeaveRequest.idempotency_key == idempotency_key,
            )
        )

    def find_pending_action_for_update(
        self,
        confirmation_token: str,
    ) -> PendingLeaveAction | None:
        """锁定并返回待确认操作供最终执行。 / Locks and returns the pending action for final execution."""

        return self._session.scalar(
            select(PendingLeaveAction)
            .where(PendingLeaveAction.confirmation_token == confirmation_token)
            .with_for_update()
        )

    def has_active_overlap(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> bool:
        """判断当前用户是否已有日期重叠的有效申请。 / Checks whether the user has an overlapping active request."""

        statement = select(LeaveRequest.request_id).where(
            LeaveRequest.user_id == user_id,
            LeaveRequest.status.in_(("PENDING_APPROVAL", "SUBMITTED")),
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
        return self._session.scalar(statement) is not None

    def reserve_balance(
        self,
        user_id: str,
        days: float,
        updated_at: datetime,
    ) -> bool:
        """仅在余额仍足够时原子扣减并预留天数。 / Atomically deducts and reserves days only when the balance remains sufficient."""

        statement = (
            update(LeaveBalance)
            .where(
                LeaveBalance.user_id == user_id,
                LeaveBalance.remaining_days >= days,
            )
            .values(
                remaining_days=LeaveBalance.remaining_days - days,
                updated_at=updated_at,
            )
        )
        result = self._session.execute(statement)
        return result.rowcount == 1

    def add_request(self, request: LeaveRequest) -> None:
        """将新申请加入当前事务。 / Adds the new request to the current transaction."""

        self._session.add(request)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise DuplicateIdempotencyRecordError() from exc

    def mark_pending_executed(
        self,
        action: PendingLeaveAction,
        request_id: str,
    ) -> None:
        """把确认操作标记为已执行并关联创建结果。 / Marks the pending action as executed and links the created result."""

        action.status = "EXECUTED"
        action.executed_request_id = request_id
