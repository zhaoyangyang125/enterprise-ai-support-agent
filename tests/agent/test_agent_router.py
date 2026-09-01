from app.agent.router import AgentRouter
from app.auth.context import CurrentUser
from app.schemas.chat import ChatResponse


class FakeLeaveBalanceTool:
    """记录 Agent 是否选择了余额查询 Tool。 / Records whether the agent selected the leave-balance tool."""

    def __init__(self) -> None:
        """初始化 Tool 调用记录。 / Initializes tool-call tracking."""

        self.received_user: CurrentUser | None = None

    def execute(self, current_user: CurrentUser) -> ChatResponse:
        """记录当前用户并返回余额意图结果。 / Records the current user and returns a leave-balance intent result."""

        self.received_user = current_user
        return ChatResponse(intent="leave_balance", answer="8 days")


class FakeSearchDocumentTool:
    """记录 Agent 是否选择了文档检索 Tool。 / Records whether the agent selected the document-search tool."""

    def __init__(self) -> None:
        """初始化查询和用户调用记录。 / Initializes query and user call tracking."""

        self.received_query: str | None = None
        self.received_user: CurrentUser | None = None

    def execute(self, query: str, current_user: CurrentUser) -> ChatResponse:
        """记录查询与当前用户并返回知识查询结果。 / Records the query and current user and returns a knowledge-query result."""

        self.received_query = query
        self.received_user = current_user
        return ChatResponse(
            intent="knowledge_query",
            answer="evidence answer",
            evidence_found=True,
        )


def test_router_selects_leave_balance_tool() -> None:
    """验证余额问题只调用余额 Tool。 / Verifies a balance question invokes only the leave-balance tool."""

    leave_tool = FakeLeaveBalanceTool()
    search_tool = FakeSearchDocumentTool()
    router = AgentRouter(leave_tool, search_tool)
    user = CurrentUser(user_id="U001")

    result = router.route("我的剩余年假是多少？", user)

    assert result.intent == "leave_balance"
    assert leave_tool.received_user == user
    assert search_tool.received_query is None


def test_router_selects_document_search_tool() -> None:
    """验证公司规则问题只调用文档检索 Tool。 / Verifies a company-policy question invokes only the document-search tool."""

    leave_tool = FakeLeaveBalanceTool()
    search_tool = FakeSearchDocumentTool()
    router = AgentRouter(leave_tool, search_tool)
    user = CurrentUser(user_id="U001")

    result = router.route("国内出差住宿费上限是多少？", user)

    assert result.intent == "knowledge_query"
    assert search_tool.received_query == "国内出差住宿费上限是多少？"
    assert search_tool.received_user == user
    assert leave_tool.received_user is None
