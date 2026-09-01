from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import LeaveBalance, User
from app.db.session import SessionFactory, create_schema

DEVELOPMENT_USER_ID = "U001"
DEVELOPMENT_REMAINING_DAYS = 8.0


def seed_development_data() -> None:
    """为本地开发创建或重置固定的年假测试数据。 / Creates or resets deterministic leave data for local development."""

    create_schema()

    with SessionFactory() as session:
        user = session.get(User, DEVELOPMENT_USER_ID)
        if user is None:
            session.add(User(user_id=DEVELOPMENT_USER_ID))

        statement = select(LeaveBalance).where(
            LeaveBalance.user_id == DEVELOPMENT_USER_ID
        )
        leave_balance = session.scalar(statement)

        if leave_balance is None:
            leave_balance = LeaveBalance(
                user_id=DEVELOPMENT_USER_ID,
                remaining_days=DEVELOPMENT_REMAINING_DAYS,
                updated_at=datetime.now(UTC),
            )
            session.add(leave_balance)
        else:
            leave_balance.remaining_days = DEVELOPMENT_REMAINING_DAYS
            leave_balance.updated_at = datetime.now(UTC)

        session.commit()


if __name__ == "__main__":
    seed_development_data()
    print(
        "Seeded development leave balance: "
        f"{DEVELOPMENT_USER_ID} = {DEVELOPMENT_REMAINING_DAYS} day(s)"
    )
