from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """作为所有 SQLAlchemy 数据库模型的基类。 / Serves as the base class for all SQLAlchemy database models."""

    pass


class User(Base):
    """表示企业系统中的用户记录。 / Represents a user record in the enterprise system."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    leave_balance: Mapped["LeaveBalance | None"] = relationship(
        back_populates="user",
        uselist=False,
    )


class LeaveBalance(Base):
    """表示用户当前的年假余额记录。 / Represents a user's current leave-balance record."""

    __tablename__ = "leave_balances"

    balance_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id"),
        unique=True,
        nullable=False,
    )
    remaining_days: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    user: Mapped[User] = relationship(back_populates="leave_balance")
