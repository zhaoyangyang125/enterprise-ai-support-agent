import pytest
from app.auth.context import CurrentUser
from app.schemas.leave_balance import LeaveBalanceResponse
from app.tools.get_leave_balance_tool import GetLeaveBalanceTool


@pytest.mark.parametrize('days', [8.0, 0.0, 7.5])
def test_leave_tool_japanese_response_and_unchanged_payload(days: float) -> None:
    """日语固定回答保持结构并准确表示零余额与半日。"""
    user = CurrentUser(user_id='U001')

    class Service:
        def get_my_leave_balance(self, current_user):
            assert current_user == user
            return LeaveBalanceResponse(remaining_days=days)

    response = GetLeaveBalanceTool(Service()).execute(user)
    assert response.answer == f'有給休暇の残日数は{days:g}日です。'
    assert response.intent == 'leave_balance'
    assert response.leave_balance.remaining_days == days
    assert response.leave_balance.unit == 'day'
