"""在文件读取之前执行文档授权。 / Authorizes before image access."""

from app.auth.context import CurrentUser
from app.document_processing.storage import LocalImageAssetStorage
from app.repositories.document_repository import SqlAlchemyDocumentRepository
from app.services.authorization_service import AuthorizationService


class ImageAssetService:
    """复用版本权限和图片存储，不接受任意路径。 / Reuses version permissions and storage."""

    def __init__(self, authorization: AuthorizationService,
                 repository: SqlAlchemyDocumentRepository,
                 storage: LocalImageAssetStorage) -> None:
        """接收授权、版本查询和本地存储。 / Receives dependencies."""
        self._authorization = authorization
        self._repository = repository
        self._storage = storage

    def read(self, user: CurrentUser, document_id: str,
             version_id: str, image_id: str) -> tuple[bytes, str]:
        """校验版本权限和归属后读取图片，返回内容和类型。 / Returns authorized bytes and MIME."""
        allowed = self._authorization.get_readable_document_version_ids(user)
        if version_id not in allowed:
            raise PermissionError("Image access denied")
        owner = self._repository.find_version_document_id(version_id)
        if owner != document_id:
            raise FileNotFoundError("Image not found")
        path = self._storage.find(document_id, version_id, image_id)
        if path is None:
            raise FileNotFoundError("Image not found")
        mime_types = {".png": "image/png", ".jpg": "image/jpeg",
                      ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp"}
        content = self._storage.read(document_id, version_id, image_id)
        return content, mime_types[path.suffix]
