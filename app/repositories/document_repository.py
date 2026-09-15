from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentPermission, DocumentVersion


class SqlAlchemyDocumentRepository:
    """在 Business DB 中维护文档、版本和处理状态。 / Maintains document, version, and processing status in the business database."""

    def __init__(self, session: Session) -> None:
        """保存文档管理使用的数据库会话。 / Stores the database session used for document management."""

        self._session = session

    def start_processing(
        self,
        document_id: str,
        title: str,
        document_version_id: str,
        version_label: str,
    ) -> None:
        """创建或更新版本并将状态提交为 processing。 / Creates or updates a version and commits its status as processing."""

        document = self._session.get(Document, document_id)
        if document is None:
            document = Document(document_id=document_id, title=title)
            self._session.add(document)
        else:
            document.title = title
        version = self._session.get(DocumentVersion, document_version_id)
        if version is None:
            version = DocumentVersion(
                document_version_id=document_version_id,
                document_id=document_id,
                version_label=version_label,
                status="processing",
                effective_from=None,
                effective_to=None,
            )
            self._session.add(version)
        else:
            version.status = "processing"
        self._session.commit()

    def mark_status(self, document_version_id: str, status: str) -> None:
        """提交文档版本的 indexed/failed 状态。 / Commits the indexed or failed status of a document version."""

        version = self._session.get(DocumentVersion, document_version_id)
        if version is None:
            raise ValueError("Document version was not initialized")
        version.status = status
        self._session.commit()

    def find_version_document_id(self, version_id: str) -> str | None:
        """查询版本所属文档，用于核对图片来源。 / Finds the owning document."""
        version = self._session.get(DocumentVersion, version_id)
        if version is None:
            return None
        return version.document_id

    def grant_user_read(self, document_id: str, user_id: str) -> None:
        """幂等地授予指定用户对文档的读取权限。 / Idempotently grants a user read access to a document."""

        existing = self._session.scalar(
            select(DocumentPermission).where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.subject_type == "user",
                DocumentPermission.subject_id == user_id,
                DocumentPermission.action == "read",
            )
        )
        if existing is None:
            self._session.add(
                DocumentPermission(
                    document_id=document_id,
                    subject_type="user",
                    subject_id=user_id,
                    action="read",
                )
            )
            self._session.commit()

    def list_versions(
        self,
        limit: int = 50,
    ) -> list[tuple[DocumentVersion, str]]:
        """按编号倒序返回文档版本和对应标题。 / Returns document versions and titles in descending identifier order."""

        rows = self._session.execute(
            select(DocumentVersion, Document.title)
            .join(Document, Document.document_id == DocumentVersion.document_id)
            .order_by(DocumentVersion.document_version_id.desc())
            .limit(limit)
        ).all()
        return [(version, title) for version, title in rows]
