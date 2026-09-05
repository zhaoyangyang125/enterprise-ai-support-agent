from pathlib import Path
import shutil


class LocalDocumentStorage:
    """按文档和版本保存可审计、可重新解析的原文件。 / Stores auditable and re-processable originals by document and version."""

    def __init__(self, root: Path | str) -> None:
        """设置本地原文件存储根目录。 / Sets the local original-document storage root."""

        self._root = Path(root)

    def store(
        self,
        source_path: Path,
        document_id: str,
        document_version_id: str,
        file_name: str | None = None,
    ) -> Path:
        """复制原文件到稳定的文档版本目录。 / Copies the original file into a stable document-version directory."""

        target_directory = self._root / document_id / document_version_id
        target_directory.mkdir(parents=True, exist_ok=True)
        safe_file_name = Path(file_name or source_path.name).name
        target_path = target_directory / safe_file_name
        shutil.copy2(source_path, target_path)
        return target_path
