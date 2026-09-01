from datetime import date

from app.auth.context import CurrentUser
from app.schemas.leave_request import LeaveRequestPreview, LeaveRequestResponse
from app.services.leave_request_service import LeaveRequestService


class CreateLeaveRequestTool:
    """将 Agent 的结构化年假申请安全桥接到写入 Service。 / Safely bridges the agent's structured leave request to the write service."""

    def __init__(self, service: LeaveRequestService) -> None:
        """接收已经实现全部安全规则的写入 Service。 / Receives the write service that owns all safety rules."""

        self._service = service

    def prepare(
        self,
        current_user: CurrentUser,
        start_date: date,
        end_date: date,
    ) -> LeaveRequestPreview:
        """生成 Agent 必须向用户展示的确认预览。 / Creates the confirmation preview that the agent must show to the user."""

        return self._service.prepare(current_user, start_date, end_date)

    def confirm(
        self,
        current_user: CurrentUser,
        confirmation_token: str,
        confirmed: bool,
        idempotency_key: str,
    ) -> LeaveRequestResponse:
        """把明确确认和幂等键交给 Service 完成安全写入。 / Passes explicit confirmation and the idempotency key to the service for safe writing."""

        return self._service.confirm(
            current_user=current_user,
            confirmation_token=confirmation_token,
            confirmed=confirmed,
            idempotency_key=idempotency_key,
        )
