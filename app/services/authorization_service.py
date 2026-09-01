from datetime import datetime

from app.auth.context import CurrentUser
from app.repositories.document_access_repository import DocumentAccessRepository


class AuthorizationService:
    """执行不依赖 LLM 的确定性资源授权。 / Performs deterministic resource authorization without relying on an LLM."""

    def __init__(self, repository: DocumentAccessRepository) -> None:
        """接收访问 Business DB 权限数据所需的 Repository。 / Receives the repository needed to access permission data in the business database."""

        self._repository = repository

    def get_readable_document_version_ids(
        self,
        current_user: CurrentUser,
        at: datetime | None = None,
    ) -> frozenset[str]:
        """取得当前用户可读且有效的文档版本编号。 / Gets active document-version IDs readable by the current user."""

        return self._repository.find_readable_active_version_ids(current_user, at)
