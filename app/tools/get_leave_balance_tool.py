from app.auth.context import CurrentUser
from app.schemas.chat import ChatResponse
from app.services.leave_service import LeaveService


class GetLeaveBalanceTool:
    """将 Agent 的余额查询安全地桥接到 LeaveService。 / Safely bridges the agent's balance query to LeaveService."""

    def __init__(self, service: LeaveService) -> None:
        """接收可复用的年假业务 Service。 / Receives the reusable leave business service."""

        self._service = service

    def execute(self, current_user: CurrentUser) -> ChatResponse:
        """使用认证用户身份查询其本人余额并转换为 Tool 结果。 / Queries the authenticated user's own balance and converts it to a tool result."""

        balance = self._service.get_my_leave_balance(current_user)
        return ChatResponse(
            intent="leave_balance",
            answer=f"您的剩余年假为 {balance.remaining_days:g} 天。",
            leave_balance=balance,
        )
