from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
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


class Document(Base):
    """表示一份逻辑上的公司文档。 / Represents one logical company document."""

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)


class DocumentVersion(Base):
    """表示公司文档的一个可管理版本。 / Represents one managed version of a company document."""

    __tablename__ = "document_versions"

    document_version_id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.document_id"),
        nullable=False,
    )
    version_label: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DocumentPermission(Base):
    """表示用户、部门或角色对文档的确定性权限。 / Represents deterministic document access for a user, department, or role."""

    __tablename__ = "document_permissions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "subject_type",
            "subject_id",
            "action",
            name="uq_document_permission_subject_action",
        ),
    )

    permission_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.document_id"),
        nullable=False,
    )
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False, default="read")
