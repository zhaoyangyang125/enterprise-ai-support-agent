from datetime import date, datetime

from app.auth.context import CurrentUser
from app.schemas.leave_request import LeaveRequestPreview, LeaveRequestResponse
from app.tools.create_leave_request_tool import CreateLeaveRequestTool


class FakeLeaveRequestService:
    """记录写入 Tool 是否完整转发结构化安全参数。 / Records whether the write tool forwards all structured safety parameters."""

    def __init__(self) -> None:
        """初始化 Prepare 和 Confirm 调用记录。 / Initializes prepare and confirm call tracking."""

        self.prepare_call: tuple[CurrentUser, date, date] | None = None
        self.confirm_call: tuple[CurrentUser, str, bool, str] | None = None

    def prepare(
        self,
        current_user: CurrentUser,
        start_date: date,
        end_date: date,
    ) -> LeaveRequestPreview:
        """记录 Prepare 调用并返回固定预览。 / Records the prepare call and returns a fixed preview."""

        self.prepare_call = (current_user, start_date, end_date)
        return LeaveRequestPreview(
            confirmation_token="confirmation-token-001",
            start_date=start_date,
            end_date=end_date,
            requested_days=3.0,
            current_balance=8.0,
            remaining_after_request=5.0,
            approval_required=False,
            expires_at=datetime(2026, 9, 1, 12, 15, 0),
        )

    def confirm(
        self,
        current_user: CurrentUser,
        confirmation_token: str,
        confirmed: bool,
        idempotency_key: str,
    ) -> LeaveRequestResponse:
        """记录 Confirm 调用并返回固定结果。 / Records the confirm call and returns a fixed result."""

        self.confirm_call = (
            current_user,
            confirmation_token,
            confirmed,
            idempotency_key,
        )
        return LeaveRequestResponse(
            request_id="LR-001",
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 9),
            requested_days=3.0,
            remaining_after_request=5.0,
            approval_required=False,
            status="SUBMITTED",
        )


def test_tool_forwards_prepare_and_confirm_to_same_service() -> None:
    """验证 Tool 不复制业务逻辑，只完整转发两个阶段。 / Verifies the tool copies no business logic and fully forwards both stages."""

    service = FakeLeaveRequestService()
    tool = CreateLeaveRequestTool(service)
    user = CurrentUser(user_id="U001")

    preview = tool.prepare(user, date(2026, 9, 7), date(2026, 9, 9))
    result = tool.confirm(user, preview.confirmation_token, True, "idem-key-001")

    assert service.prepare_call == (
        user,
        date(2026, 9, 7),
        date(2026, 9, 9),
    )
    assert service.confirm_call == (
        user,
        "confirmation-token-001",
        True,
        "idem-key-001",
    )
    assert result.request_id == "LR-001"
