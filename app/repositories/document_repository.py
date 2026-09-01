from sqlalchemy.orm import Session

from app.db.models import Document, DocumentVersion


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
