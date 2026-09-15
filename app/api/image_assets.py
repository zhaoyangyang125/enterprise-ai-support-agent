"""提供受文档权限控制的图片响应。 / Provides authorized image responses."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import Response

from app.auth.context import CurrentUser, get_current_user
from app.dependencies import get_image_asset_service
from app.services.image_asset_service import ImageAssetService

router = APIRouter(prefix="/api/documents", tags=["image-assets"])
DocumentId = Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")]
ImageId = Annotated[str, Path(pattern=r"^img_[0-9a-f]{64}$")]


@router.get("/{document_id}/versions/{version_id}/assets/{image_id}")
def read_image(
    document_id: DocumentId, version_id: DocumentId, image_id: ImageId,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ImageAssetService, Depends(get_image_asset_service)],
) -> Response:
    """每次访问重新授权，不暴露服务器路径。 / Reauthorizes every request."""
    try:
        result = service.read(user, document_id, version_id, image_id)
    except PermissionError:
        raise HTTPException(403, "无权读取此图片。") from None
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "图片不存在。") from None
    content = result[0]
    mime_type = result[1]
    return Response(content=content, media_type=mime_type,
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
