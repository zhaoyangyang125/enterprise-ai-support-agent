from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.context import CurrentUser
from app.db.models import Base, Document, DocumentPermission, DocumentVersion
from app.repositories.document_access_repository import (
    SqlAlchemyDocumentAccessRepository,
)


CHECKED_AT = datetime(2026, 9, 1, 12, 0, 0)


def make_session() -> Session:
    """创建隔离的内存 Business DB 测试会话。 / Creates an isolated in-memory business-database session."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def add_document_version(
    session: Session,
    document_id: str,
    version_id: str,
    status: str = "active",
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
) -> None:
    """向测试数据库添加文档及其版本。 / Adds a document and one version to the test database."""

    session.add(Document(document_id=document_id, title=document_id))
    session.add(
        DocumentVersion(
            document_version_id=version_id,
            document_id=document_id,
            version_label="v1",
            status=status,
            effective_from=effective_from,
            effective_to=effective_to,
        )
    )


def add_permission(
    session: Session,
    document_id: str,
    subject_type: str,
    subject_id: str,
) -> None:
    """向测试数据库添加读取权限。 / Adds a read permission to the test database."""

    session.add(
        DocumentPermission(
            document_id=document_id,
            subject_type=subject_type,
            subject_id=subject_id,
            action="read",
        )
    )


def test_explicit_user_permission_returns_active_version() -> None:
    """验证用户显式权限可以读取当前有效版本。 / Verifies explicit user permission can read the current active version."""

    with make_session() as session:
        add_document_version(session, "DOC-USER", "DOC-USER-V1")
        add_permission(session, "DOC-USER", "user", "U001")
        session.commit()
        repository = SqlAlchemyDocumentAccessRepository(session)

        result = repository.find_readable_active_version_ids(
            CurrentUser(user_id="U001"),
            CHECKED_AT,
        )

    assert result == frozenset({"DOC-USER-V1"})


def test_department_and_role_permissions_return_only_matching_versions() -> None:
    """验证部门和角色权限只返回匹配范围的版本。 / Verifies department and role permissions return only matching versions."""

    with make_session() as session:
        add_document_version(session, "DOC-DEPT", "DOC-DEPT-V1")
        add_document_version(session, "DOC-ROLE", "DOC-ROLE-V1")
        add_document_version(session, "DOC-OTHER", "DOC-OTHER-V1")
        add_permission(session, "DOC-DEPT", "department", "D-SALES")
        add_permission(session, "DOC-ROLE", "role", "MANAGER")
        add_permission(session, "DOC-OTHER", "department", "D-FINANCE")
        session.commit()
        repository = SqlAlchemyDocumentAccessRepository(session)

        result = repository.find_readable_active_version_ids(
            CurrentUser(
                user_id="U001",
                department_id="D-SALES",
                role_ids=frozenset({"MANAGER"}),
            ),
            CHECKED_AT,
        )

    assert result == frozenset({"DOC-DEPT-V1", "DOC-ROLE-V1"})


def test_inactive_expired_future_and_unauthorized_versions_are_excluded() -> None:
    """验证无权限、非活动、过期和未来版本均被排除。 / Verifies unauthorized, inactive, expired, and future versions are excluded."""

    with make_session() as session:
        add_document_version(session, "DOC-INACTIVE", "V-INACTIVE", status="inactive")
        add_document_version(
            session,
            "DOC-EXPIRED",
            "V-EXPIRED",
            effective_to=datetime(2026, 8, 31),
        )
        add_document_version(
            session,
            "DOC-FUTURE",
            "V-FUTURE",
            effective_from=datetime(2026, 9, 2),
        )
        add_document_version(session, "DOC-OTHER", "V-OTHER")
        for document_id in ("DOC-INACTIVE", "DOC-EXPIRED", "DOC-FUTURE"):
            add_permission(session, document_id, "user", "U001")
        add_permission(session, "DOC-OTHER", "user", "U999")
        session.commit()
        repository = SqlAlchemyDocumentAccessRepository(session)

        result = repository.find_readable_active_version_ids(
            CurrentUser(user_id="U001"),
            CHECKED_AT,
        )

    assert result == frozenset()
