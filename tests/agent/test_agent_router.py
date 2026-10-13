from app.agent.router import AgentRouter
from app.auth.context import CurrentUser
from app.schemas.chat import ChatResponse
from app.schemas.rag import RetrievalFilter


class FakeLeaveBalanceTool:
    """记录 Agent 是否选择了余额查询 Tool。 / Records whether the agent selected the leave-balance tool."""

    def __init__(self) -> None:
        """初始化 Tool 调用记录。 / Initializes tool-call tracking."""

        self.received_user: CurrentUser | None = None
        self.received_filter: RetrievalFilter | None = None

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

    def execute(
        self,
        query: str,
        current_user: CurrentUser,
        metadata_filter: RetrievalFilter | None = None,
    ) -> ChatResponse:
        """记录查询与当前用户并返回知识查询结果。 / Records the query and current user and returns a knowledge-query result."""

        self.received_query = query
        self.received_user = current_user
        self.received_filter = metadata_filter
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
    assert search_tool.received_filter is None
    assert leave_tool.received_user is None


def test_router_passes_metadata_filter_only_to_document_search() -> None:
    """验证知识查询的 metadata 条件被传给文档 Tool。 / Verifies knowledge-query metadata conditions are passed to the document tool."""

    leave_tool = FakeLeaveBalanceTool()
    search_tool = FakeSearchDocumentTool()
    router = AgentRouter(leave_tool, search_tool)
    metadata_filter = RetrievalFilter(sheets=frozenset({"CAN信号"}))

    router.route(
        "VehicleSpeedの期待値",
        CurrentUser(user_id="U001"),
        metadata_filter,
    )

    assert search_tool.received_filter == metadata_filter
    assert leave_tool.received_user is None


import pytest


@pytest.mark.parametrize("message", [
    "有給残日数を教えてください。",
    "私の有給休暇はあと何日ありますか？",
    "有給休暇は何日残っていますか？",
    "有給の残りを確認したいです。",
    "年休の残日数はいくつですか？",
    "有給休暇はあと　何日ありますか？",
])
def test_japanese_balance_intent(message: str) -> None:
    """常见日语余额问题只调用本人余额Tool。"""
    leave, search = FakeLeaveBalanceTool(), FakeSearchDocumentTool()
    result = AgentRouter(leave, search).route(message, CurrentUser(user_id="U001"))
    assert result.intent == "leave_balance"
    assert search.received_query is None


@pytest.mark.parametrize("message", [
    "有給休暇の取得ルールを教えてください",
    "有給休暇の申請方法を教えてください",
    "有給休暇の残日数の繰り越しルールを教えてください",
    "有給休暇の付与日数は何日ですか？",
    "有給休暇の取得上限は何日ですか？",
    "有給休暇を申請したい。残りは何日？",
])
def test_japanese_leave_policy_stays_in_rag(message: str) -> None:
    """规则与写入意图不误触发余额Tool。"""
    leave, search = FakeLeaveBalanceTool(), FakeSearchDocumentTool()
    result = AgentRouter(leave, search).route(message, CurrentUser(user_id="U001"))
    assert result.intent == "knowledge_query"
    assert leave.received_user is None
