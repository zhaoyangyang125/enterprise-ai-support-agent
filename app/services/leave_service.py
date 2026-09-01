from app.auth.context import CurrentUser
from app.repositories.leave_repository import LeaveRepository
from app.schemas.leave_balance import LeaveBalanceResponse
from app.services.errors import LeaveBalanceNotFoundError


class LeaveService:
    """执行年假相关的业务规则和用例流程。 / Executes leave-related business rules and use-case flows."""

    def __init__(self, repository: LeaveRepository) -> None:
        """接收 Service 访问年假数据所需的 Repository。 / Receives the repository required for leave-data access."""

        self._repository = repository

    def get_my_leave_balance(
        self,
        current_user: CurrentUser,
    ) -> LeaveBalanceResponse:
        """查询当前用户的年假余额并转换为业务响应。 / Retrieves the current user's leave balance and converts it to a business response."""

        leave_balance = self._repository.find_by_user_id(current_user.user_id)
        if leave_balance is None:
            raise LeaveBalanceNotFoundError()

        return LeaveBalanceResponse(remaining_days=leave_balance.remaining_days)
