from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth.context import CurrentUser
from app.db.models import DocumentPermission, DocumentVersion


class DocumentAccessRepository(Protocol):
    """定义查询当前用户可读文档版本所需的接口。 / Defines the interface for finding document versions readable by the current user."""

    def find_readable_active_version_ids(
        self,
        current_user: CurrentUser,
        at: datetime | None = None,
    ) -> frozenset[str]:
        """返回当前时点可读且有效的文档版本编号。 / Returns readable and active document-version IDs at the given time."""

        ...


class SqlAlchemyDocumentAccessRepository:
    """使用 Business DB 计算文档权限和有效版本范围。 / Uses the business database to calculate document access and active versions."""

    def __init__(self, session: Session) -> None:
        """保存权限查询使用的数据库会话。 / Stores the database session used by access queries."""

        self._session = session

    def find_readable_active_version_ids(
        self,
        current_user: CurrentUser,
        at: datetime | None = None,
    ) -> frozenset[str]:
        """按用户、部门和角色权限返回有效版本编号。 / Returns active version IDs allowed by user, department, or role permissions."""

        checked_at = at or datetime.now(timezone.utc).replace(tzinfo=None)
        subject_conditions = [
            and_(
                DocumentPermission.subject_type == "user",
                DocumentPermission.subject_id == current_user.user_id,
            )
        ]
        if current_user.department_id is not None:
            subject_conditions.append(
                and_(
                    DocumentPermission.subject_type == "department",
                    DocumentPermission.subject_id == current_user.department_id,
                )
            )
        if current_user.role_ids:
            subject_conditions.append(
                and_(
                    DocumentPermission.subject_type == "role",
                    DocumentPermission.subject_id.in_(current_user.role_ids),
                )
            )

        statement = (
            select(DocumentVersion.document_version_id)
            .join(
                DocumentPermission,
                DocumentPermission.document_id == DocumentVersion.document_id,
            )
            .where(
                DocumentPermission.action == "read",
                or_(*subject_conditions),
                DocumentVersion.status == "active",
                or_(
                    DocumentVersion.effective_from.is_(None),
                    DocumentVersion.effective_from <= checked_at,
                ),
                or_(
                    DocumentVersion.effective_to.is_(None),
                    DocumentVersion.effective_to >= checked_at,
                ),
            )
            .distinct()
        )
        return frozenset(self._session.scalars(statement).all())
