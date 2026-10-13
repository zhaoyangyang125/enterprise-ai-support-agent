import re
import unicodedata

from app.auth.context import CurrentUser
from app.schemas.chat import ChatResponse
from app.schemas.rag import RetrievalFilter
from app.tools.get_leave_balance_tool import GetLeaveBalanceTool
from app.tools.search_document_tool import SearchDocumentTool


class AgentRouter:
    """识别只读请求意图并选择受控 Tool。 / Identifies read-only request intent and selects a controlled tool."""

    _LEAVE_BALANCE_TERMS = (
        "年假余额",
        "剩余年假",
        "年假还剩",
        "有給残日数",
        "有給の残り",
        "leave balance",
    )

    def __init__(
        self,
        leave_balance_tool: GetLeaveBalanceTool,
        search_document_tool: SearchDocumentTool,
    ) -> None:
        """接收 Agent 可以选择的两个只读 Tool。 / Receives the two read-only tools available to the agent."""

        self._leave_balance_tool = leave_balance_tool
        self._search_document_tool = search_document_tool

    def route(
        self,
        message: str,
        current_user: CurrentUser,
        metadata_filter: RetrievalFilter | None = None,
    ) -> ChatResponse:
        """将余额意图路由到业务 Tool，其余只读问题路由到文档检索。 / Routes balance intent to its business tool and other read queries to document search."""

        normalized = unicodedata.normalize("NFKC", message).casefold()
        # 日语必须同时包含休假对象和余额意图；规则/申请问题优先保持文档检索。
        japanese_balance = (
            any(term in normalized for term in ("有給", "年休"))
            and not any(term in normalized for term in (
                "ルール", "規定", "取得方法", "申請", "繰越", "繰り越", "付与", "上限",
            ))
            and bool(re.search(r"残(?:り|日数|数)?|あと\s*何日|何日\s*残|残高", normalized))
        )
        legacy_balance = any(
            term.casefold() in normalized for term in self._LEAVE_BALANCE_TERMS
            if term not in ("有給残日数", "有給の残り")
        )
        if japanese_balance or legacy_balance:
            return self._leave_balance_tool.execute(current_user)
        return self._search_document_tool.execute(
            message,
            current_user,
            metadata_filter,
        )
