from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LeaveBalance


class LeaveRepository(Protocol):
    """定义 Service 访问年假余额数据所需的接口。 / Defines the data-access interface required by the leave service."""

    def find_by_user_id(self, user_id: str) -> LeaveBalance | None:
        """按用户编号查找当前年假余额记录。 / Finds the current leave-balance record by user ID."""

        ...


class SqlAlchemyLeaveRepository:
    """使用 SQLAlchemy 从业务数据库读取年假余额。 / Reads leave balances from the business database with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """保存本次数据访问使用的数据库会话。 / Stores the database session used for this data-access operation."""

        self._session = session

    def find_by_user_id(self, user_id: str) -> LeaveBalance | None:
        """按用户编号查询年假余额，无记录时返回 None。 / Queries leave balance by user ID and returns None when absent."""

        statement = select(LeaveBalance).where(LeaveBalance.user_id == user_id)
        return self._session.scalar(statement)
