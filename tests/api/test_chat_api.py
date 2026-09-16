from collections.abc import Iterator

from fastapi.testclient import TestClient
import pytest

from app.auth.context import CurrentUser
from app.dependencies import get_agent_router
from app.main import app
from app.schemas.chat import ChatResponse
from app.schemas.rag import RetrievalFilter


class FakeAgentRouter:
    """为 Chat API 测试返回固定结果并记录输入。 / Returns a fixed result and records input for Chat API tests."""

    def __init__(self) -> None:
        """初始化消息和认证上下文调用记录。 / Initializes message and authentication-context tracking."""

        self.received_message: str | None = None
        self.received_user: CurrentUser | None = None
        self.received_filter: RetrievalFilter | None = None

    def route(
        self,
        message: str,
        current_user: CurrentUser,
        metadata_filter: RetrievalFilter | None = None,
    ) -> ChatResponse:
        """记录消息和当前用户并返回固定知识回答。 / Records the message and current user and returns a fixed knowledge answer."""

        self.received_message = message
        self.received_user = current_user
        self.received_filter = metadata_filter
        return ChatResponse(
            intent="knowledge_query",
            answer="国内出差住宿费上限为每晚 10,000 日元。",
            evidence_found=True,
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    """在每个 Chat API 测试后清除依赖替换。 / Clears dependency overrides after every Chat API test."""

    try:
        yield
    finally:
        app.dependency_overrides.clear()


def test_chat_passes_authenticated_context_to_agent() -> None:
    """验证 Chat API 将完整认证上下文交给 Agent。 / Verifies the Chat API passes the complete authentication context to the agent."""

    fake_router = FakeAgentRouter()

    def override_get_agent_router() -> FakeAgentRouter:
        """为当前测试提供 Fake Agent Router。 / Provides the fake agent router for this test."""

        return fake_router

    app.dependency_overrides[get_agent_router] = override_get_agent_router
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        headers={
            "X-User-Id": "U001",
            "X-Department-Id": "D-SALES",
            "X-Role-Ids": "EMPLOYEE,MANAGER",
        },
        json={
            "message": "国内出差住宿费上限是多少？",
            "retrieval_filter": {
                "content_types": ["table"],
                "sheets": ["出張規定"],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["intent"] == "knowledge_query"
    assert fake_router.received_message == "国内出差住宿费上限是多少？"
    assert fake_router.received_user == CurrentUser(
        user_id="U001",
        department_id="D-SALES",
        role_ids=frozenset({"EMPLOYEE", "MANAGER"}),
    )
    assert fake_router.received_filter == RetrievalFilter(
        content_types=frozenset({"table"}),
        sheets=frozenset({"出張規定"}),
    )


def test_chat_requires_authentication_context() -> None:
    """验证 Chat API 缺少认证用户时拒绝请求。 / Verifies the Chat API rejects a request without an authenticated user."""

    client = TestClient(app)
    response = client.post("/api/chat", json={"message": "公司规则是什么？"})

    assert response.status_code == 422


def test_chat_rejects_empty_message() -> None:
    """验证 Chat API 拒绝空消息。 / Verifies the Chat API rejects an empty message."""

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        headers={"X-User-Id": "U001"},
        json={"message": ""},
    )

    assert response.status_code == 422


def test_chat_rejects_unknown_content_type_filter() -> None:
    """验证 API 拒绝不在白名单内的内容类型。 / Verifies the API rejects content types outside the allowlist."""

    fake_router = FakeAgentRouter()

    def override_get_agent_router() -> FakeAgentRouter:
        """为当前测试提供 Fake Agent Router。 / Provides the fake agent router for this test."""

        return fake_router

    app.dependency_overrides[get_agent_router] = override_get_agent_router
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        headers={"X-User-Id": "U001"},
        json={
            "message": "公司规则是什么？",
            "retrieval_filter": {"content_types": ["unknown_type"]},
        },
    )

    assert response.status_code == 422
    assert fake_router.received_message is None
