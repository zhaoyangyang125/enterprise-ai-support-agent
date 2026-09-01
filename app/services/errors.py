class LeaveBalanceNotFoundError(Exception):
    """表示当前用户的年假余额记录不存在。 / Indicates that the current user's leave-balance record does not exist."""


class LeaveRequestError(Exception):
    """作为年假申请业务异常的共同基类。 / Serves as the common base for leave-request business errors."""


class InvalidLeaveDateRangeError(LeaveRequestError):
    """表示申请日期顺序无效或不含工作日。 / Indicates an invalid date order or a range without business days."""


class InsufficientLeaveBalanceError(LeaveRequestError):
    """表示当前余额不足以创建申请。 / Indicates that the current balance is insufficient for the request."""


class OverlappingLeaveRequestError(LeaveRequestError):
    """表示申请日期与现有有效申请重叠。 / Indicates that requested dates overlap an existing active request."""


class ConfirmationRequiredError(LeaveRequestError):
    """表示用户没有提供明确确认。 / Indicates that the user did not provide explicit confirmation."""


class PendingLeaveActionNotFoundError(LeaveRequestError):
    """表示确认令牌不存在或不属于当前用户。 / Indicates that the confirmation token is absent or not owned by the current user."""


class PendingLeaveActionExpiredError(LeaveRequestError):
    """表示确认操作已经过期。 / Indicates that the pending confirmation has expired."""


class PendingLeaveActionAlreadyUsedError(LeaveRequestError):
    """表示确认令牌已被另一次操作消费。 / Indicates that the confirmation token was consumed by another operation."""


class IdempotencyConflictError(LeaveRequestError):
    """表示同一幂等键被用于不同业务操作。 / Indicates that the same idempotency key was used for a different operation."""
