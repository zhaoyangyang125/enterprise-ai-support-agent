from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import (
    Document,
    DocumentPermission,
    DocumentVersion,
    LeaveBalance,
    User,
)
from app.db.session import SessionFactory, create_schema

DEVELOPMENT_USER_ID = "U001"
DEVELOPMENT_REMAINING_DAYS = 8.0
DEMO_DOCUMENT_ID = "TRAVEL_POLICY"
DEMO_DOCUMENT_VERSION_ID = "TRAVEL_POLICY-V1"


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

        document = session.get(Document, DEMO_DOCUMENT_ID)
        if document is None:
            session.add(
                Document(
                    document_id=DEMO_DOCUMENT_ID,
                    title="国内出差规定 / Domestic Travel Policy",
                )
            )

        document_version = session.get(DocumentVersion, DEMO_DOCUMENT_VERSION_ID)
        if document_version is None:
            session.add(
                DocumentVersion(
                    document_version_id=DEMO_DOCUMENT_VERSION_ID,
                    document_id=DEMO_DOCUMENT_ID,
                    version_label="v1",
                    status="active",
                    effective_from=None,
                    effective_to=None,
                )
            )

        permission = session.scalar(
            select(DocumentPermission).where(
                DocumentPermission.document_id == DEMO_DOCUMENT_ID,
                DocumentPermission.subject_type == "user",
                DocumentPermission.subject_id == DEVELOPMENT_USER_ID,
                DocumentPermission.action == "read",
            )
        )
        if permission is None:
            session.add(
                DocumentPermission(
                    document_id=DEMO_DOCUMENT_ID,
                    subject_type="user",
                    subject_id=DEVELOPMENT_USER_ID,
                    action="read",
                )
            )

        session.commit()


if __name__ == "__main__":
    seed_development_data()
    print(
        "Seeded development leave balance: "
        f"{DEVELOPMENT_USER_ID} = {DEVELOPMENT_REMAINING_DAYS} day(s)"
    )
