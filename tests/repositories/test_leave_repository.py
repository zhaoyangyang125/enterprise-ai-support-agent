from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, LeaveBalance, User
from app.repositories.leave_repository import SqlAlchemyLeaveRepository


@pytest.fixture
def sqlite_session() -> Iterator[Session]:
    """为 Repository 测试提供隔离的内存 SQLite。 / Provides isolated in-memory SQLite for repository tests."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def test_find_by_user_id_returns_matching_leave_balance(
    sqlite_session: Session,
) -> None:
    """验证 Repository 能按用户编号读取余额记录。 / Verifies that the repository reads a balance by user ID."""

    sqlite_session.add(User(user_id="U001"))
    sqlite_session.add(
        LeaveBalance(
            balance_id=1,
            user_id="U001",
            remaining_days=8.0,
            updated_at=datetime.now(UTC),
        )
    )
    sqlite_session.commit()

    repository = SqlAlchemyLeaveRepository(sqlite_session)
    result = repository.find_by_user_id("U001")

    assert result is not None
    assert result.balance_id == 1
    assert result.user_id == "U001"
    assert result.remaining_days == 8.0


def test_find_by_user_id_returns_none_when_record_is_missing(
    sqlite_session: Session,
) -> None:
    """验证没有匹配记录时 Repository 返回 None。 / Verifies that the repository returns None when no record matches."""

    repository = SqlAlchemyLeaveRepository(sqlite_session)

    assert repository.find_by_user_id("U999") is None
