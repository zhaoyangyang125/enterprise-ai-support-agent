from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.auth.context import CurrentUser, get_current_user
from app.dependencies import get_document_service
from app.schemas.document import DocumentUploadResponse, DocumentVersionStatus
from app.services.document_service import DocumentService


router = APIRouter(prefix="/api/admin/documents", tags=["documents"])

_ALLOWED_SUFFIXES = frozenset({".pdf", ".xlsx"})
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_COPY_CHUNK_BYTES = 1024 * 1024


def require_document_admin(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """限制文档管理接口只能由开发阶段的 ADMIN 角色调用。 / Restricts document management APIs to the development ADMIN role."""

    if "ADMIN" not in current_user.role_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Document administration permission is required.",
        )
    return current_user


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[UploadFile, File()],
    document_id: Annotated[str, Form(min_length=1, max_length=100)],
    title: Annotated[str, Form(min_length=1, max_length=200)],
    document_version_id: Annotated[str, Form(min_length=1, max_length=100)],
    version_label: Annotated[str, Form(min_length=1, max_length=50)],
    current_user: Annotated[CurrentUser, Depends(require_document_admin)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentUploadResponse:
    """验证并同步处理一个 PDF 或 Excel 文档。 / Validates and synchronously processes one PDF or Excel document."""

    temporary_path: Path | None = None
    try:
        temporary_path = await _save_temporary_upload(file)
        result = service.ingest(
            source_path=temporary_path,
            document_id=document_id,
            title=title,
            document_version_id=document_version_id,
            version_label=version_label,
            source_name=Path(file.filename or temporary_path.name).name,
            grant_read_to_user_id=current_user.user_id,
        )
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The document could not be parsed into indexable content.",
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed.",
        ) from error
    finally:
        await file.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return DocumentUploadResponse(
        document_id=result.document_id,
        document_version_id=result.document_version_id,
        title=title,
        status="active",
        chunk_count=result.chunk_count,
    )


@router.get("", response_model=list[DocumentVersionStatus])
def list_document_versions(
    _current_user: Annotated[CurrentUser, Depends(require_document_admin)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> list[DocumentVersionStatus]:
    """返回最近的文档版本处理状态。 / Returns recent document-version processing states."""

    return service.list_versions()


async def _save_temporary_upload(file: UploadFile) -> Path:
    """限制类型和大小后，将上传流写入临时文件。 / Writes an upload stream to a temporary file after type and size validation."""

    suffix = Path(file.filename or "").suffix.casefold()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .pdf and .xlsx files are supported.",
        )

    temporary_file = NamedTemporaryFile(delete=False, suffix=suffix)
    temporary_path = Path(temporary_file.name)
    total_bytes = 0
    try:
        while content := await file.read(_COPY_CHUNK_BYTES):
            total_bytes += len(content)
            if total_bytes > _MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="The document exceeds the 10 MB upload limit.",
                )
            temporary_file.write(content)
    except Exception:
        temporary_file.close()
        temporary_path.unlink(missing_ok=True)
        raise
    else:
        temporary_file.close()

    if total_bytes == 0:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded document is empty.",
        )
    return temporary_path
