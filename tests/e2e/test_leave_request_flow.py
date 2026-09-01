from collections.abc import Iterator
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import Base, LeaveBalance, LeaveRequest, User
from app.db.session import get_db_session
from app.main import app


def test_prepare_confirm_and_retry_are_transactional_and_idempotent() -> None:
    """端到端验证 Prepare、Confirm、事务和幂等重试。 / End-to-end verifies prepare, confirm, transactionality, and idempotent retry."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(user_id="U001"))
        session.add(
            LeaveBalance(
                user_id="U001",
                remaining_days=8.0,
                updated_at=datetime(2026, 9, 1, 12, 0, 0),
            )
        )
        session.commit()

    def override_db_session() -> Iterator[Session]:
        """为端到端请求提供同一个隔离数据库。 / Provides the same isolated database to end-to-end requests."""

        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        client = TestClient(app)
        prepare_response = client.post(
            "/api/me/leave-requests/prepare",
            headers={"X-User-Id": "U001"},
            json={"start_date": "2026-09-07", "end_date": "2026-09-09"},
        )
        assert prepare_response.status_code == 200
        token = prepare_response.json()["confirmation_token"]

        headers = {
            "X-User-Id": "U001",
            "Idempotency-Key": "e2e-idempotency-001",
        }
        payload = {"confirmation_token": token, "confirmed": True}
        first_response = client.post(
            "/api/me/leave-requests",
            headers=headers,
            json=payload,
        )
        retry_response = client.post(
            "/api/me/leave-requests",
            headers=headers,
            json=payload,
        )

        assert first_response.status_code == 201
        assert retry_response.status_code == 201
        assert retry_response.json() == first_response.json()

        with Session(engine) as session:
            balance = session.scalar(
                select(LeaveBalance.remaining_days).where(
                    LeaveBalance.user_id == "U001"
                )
            )
            request_count = session.scalar(select(func.count(LeaveRequest.request_id)))

        assert balance == 5.0
        assert request_count == 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
