from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
import secrets
import uuid

from app.auth.context import CurrentUser
from app.db.models import LeaveRequest, PendingLeaveAction
from app.repositories.leave_request_repository import (
    DuplicateIdempotencyRecordError,
    LeaveRequestRepository,
)
from app.schemas.leave_request import LeaveRequestPreview, LeaveRequestResponse
from app.services.errors import (
    ConfirmationRequiredError,
    IdempotencyConflictError,
    InsufficientLeaveBalanceError,
    InvalidLeaveDateRangeError,
    LeaveBalanceNotFoundError,
    OverlappingLeaveRequestError,
    PendingLeaveActionAlreadyUsedError,
    PendingLeaveActionExpiredError,
    PendingLeaveActionNotFoundError,
)


class LeaveRequestService:
    """执行年假申请的准备、确认、最终再验证和事务写入。 / Executes leave-request preparation, confirmation, final revalidation, and transactional write."""

    def __init__(
        self,
        repository: LeaveRequestRepository,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[], str] | None = None,
        request_id_factory: Callable[[], str] | None = None,
        confirmation_ttl_minutes: int = 15,
        approval_threshold_days: float = 3.0,
    ) -> None:
        """接收数据访问、时间和唯一编号等可替换依赖。 / Receives replaceable data access, clock, and identifier dependencies."""

        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC).replace(tzinfo=None))
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._request_id_factory = request_id_factory or (lambda: str(uuid.uuid4()))
        self._confirmation_ttl = timedelta(minutes=confirmation_ttl_minutes)
        self._approval_threshold_days = approval_threshold_days

    def prepare(
        self,
        current_user: CurrentUser,
        start_date: date,
        end_date: date,
    ) -> LeaveRequestPreview:
        """验证当前状态并生成等待明确确认的申请预览。 / Validates current state and creates a request preview awaiting explicit confirmation."""

        requested_days = self._calculate_business_days(start_date, end_date)
        balance = self._repository.find_balance(current_user.user_id)
        if balance is None:
            raise LeaveBalanceNotFoundError()
        if self._repository.has_active_overlap(
            current_user.user_id,
            start_date,
            end_date,
        ):
            raise OverlappingLeaveRequestError()
        if balance.remaining_days < requested_days:
            raise InsufficientLeaveBalanceError()

        now = self._clock()
        approval_required = requested_days > self._approval_threshold_days
        action = PendingLeaveAction(
            confirmation_token=self._token_factory(),
            user_id=current_user.user_id,
            start_date=start_date,
            end_date=end_date,
            requested_days=requested_days,
            current_balance=balance.remaining_days,
            remaining_after_request=balance.remaining_days - requested_days,
            approval_required=approval_required,
            status="WAITING_CONFIRMATION",
            expires_at=now + self._confirmation_ttl,
            created_at=now,
            executed_request_id=None,
        )
        self._repository.save_pending_action(action)
        return self._to_preview(action)

    def confirm(
        self,
        current_user: CurrentUser,
        confirmation_token: str,
        confirmed: bool,
        idempotency_key: str,
    ) -> LeaveRequestResponse:
        """明确确认后在单一事务内再验证、预留余额并创建申请。 / After explicit confirmation, revalidates, reserves balance, and creates the request in one transaction."""

        if not confirmed:
            raise ConfirmationRequiredError()

        try:
            with self._repository.transaction():
                existing = self._repository.find_request_by_idempotency_key(
                    current_user.user_id,
                    idempotency_key,
                )
                if existing is not None:
                    if existing.confirmation_token != confirmation_token:
                        raise IdempotencyConflictError()
                    return self._to_response(existing)

                action = self._repository.find_pending_action_for_update(
                    confirmation_token
                )
                if action is None or action.user_id != current_user.user_id:
                    raise PendingLeaveActionNotFoundError()
                if action.status != "WAITING_CONFIRMATION":
                    raise PendingLeaveActionAlreadyUsedError()

                now = self._clock()
                if action.expires_at < now:
                    raise PendingLeaveActionExpiredError()

                requested_days = self._calculate_business_days(
                    action.start_date,
                    action.end_date,
                )
                if requested_days != action.requested_days:
                    raise InvalidLeaveDateRangeError()
                if self._repository.has_active_overlap(
                    current_user.user_id,
                    action.start_date,
                    action.end_date,
                ):
                    raise OverlappingLeaveRequestError()

                balance = self._repository.find_balance(current_user.user_id)
                if balance is None:
                    raise LeaveBalanceNotFoundError()
                if balance.remaining_days < requested_days:
                    raise InsufficientLeaveBalanceError()

                remaining_after_request = balance.remaining_days - requested_days
                if not self._repository.reserve_balance(
                    current_user.user_id,
                    requested_days,
                    now,
                ):
                    raise InsufficientLeaveBalanceError()

                approval_required = requested_days > self._approval_threshold_days
                request = LeaveRequest(
                    request_id=self._request_id_factory(),
                    user_id=current_user.user_id,
                    start_date=action.start_date,
                    end_date=action.end_date,
                    requested_days=requested_days,
                    remaining_after_request=remaining_after_request,
                    approval_required=approval_required,
                    status="PENDING_APPROVAL" if approval_required else "SUBMITTED",
                    idempotency_key=idempotency_key,
                    confirmation_token=confirmation_token,
                    created_at=now,
                )
                self._repository.add_request(request)
                self._repository.mark_pending_executed(action, request.request_id)
        except DuplicateIdempotencyRecordError:
            existing = self._repository.find_request_by_idempotency_key(
                current_user.user_id,
                idempotency_key,
            )
            if existing is None or existing.confirmation_token != confirmation_token:
                raise IdempotencyConflictError() from None
            return self._to_response(existing)

        return self._to_response(request)

    @staticmethod
    def _calculate_business_days(start_date: date, end_date: date) -> float:
        """计算包含首尾日期的周一至周五天数。 / Counts Monday-through-Friday days inclusively."""

        if start_date > end_date:
            raise InvalidLeaveDateRangeError()
        days = 0
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        if days == 0:
            raise InvalidLeaveDateRangeError()
        return float(days)

    @staticmethod
    def _to_preview(action: PendingLeaveAction) -> LeaveRequestPreview:
        """把待确认数据库记录转换为安全预览。 / Converts a pending database record into a safe preview."""

        return LeaveRequestPreview(
            confirmation_token=action.confirmation_token,
            start_date=action.start_date,
            end_date=action.end_date,
            requested_days=action.requested_days,
            current_balance=action.current_balance,
            remaining_after_request=action.remaining_after_request,
            approval_required=action.approval_required,
            expires_at=action.expires_at,
        )

    @staticmethod
    def _to_response(request: LeaveRequest) -> LeaveRequestResponse:
        """把已创建申请转换为稳定业务响应。 / Converts a created request into a stable business response."""

        return LeaveRequestResponse(
            request_id=request.request_id,
            start_date=request.start_date,
            end_date=request.end_date,
            requested_days=request.requested_days,
            remaining_after_request=request.remaining_after_request,
            approval_required=request.approval_required,
            status=request.status,
        )
