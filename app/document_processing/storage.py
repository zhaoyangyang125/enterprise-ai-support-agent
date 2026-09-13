from pathlib import Path
import hashlib
import re
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


class StoredImageAsset:
    """表示已经保存到服务器内部的派生图片。 / Represents a derived image stored internally on the server."""

    def __init__(
        self,
        image_id: str,
        path: Path,
        image_index: int,
        mime_type: str,
    ) -> None:
        """保存图片标识、内部路径、序号和媒体类型。 / Stores the image identity, internal path, index, and media type."""

        self.image_id = image_id
        self.path = path
        self.image_index = image_index
        self.mime_type = mime_type


class LocalImageAssetStorage:
    """在 DocumentVersion 的 assets 目录中保存和读取派生图片。 / Stores and reads derived images under a DocumentVersion assets directory."""

    _MIME_TYPE_SUFFIXES = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "image/webp": ".webp",
    }
    _SAFE_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
    _SAFE_IMAGE_ID = re.compile(r"^img_[0-9a-f]{64}$")

    def __init__(self, root: Path | str) -> None:
        """设置与原文存储共用的根目录。 / Sets the root directory shared with original-document storage."""

        self._root = Path(root)

    def store(
        self,
        content: bytes,
        document_id: str,
        document_version_id: str,
        image_index: int,
        mime_type: str,
    ) -> StoredImageAsset:
        """生成稳定 image_id，并把图片保存到对应文档版本。 / Generates a stable image ID and stores the image under its document version."""

        # 输入：图片字节、文档标识、版本标识、图片序号和 MIME 类型。
        # 输出：包含稳定 image_id 与服务器内部路径的 StoredImageAsset。
        # 步骤：验证输入 -> 生成 ID -> 创建 assets 目录 -> 写入图片。
        self._validate_path_segment(document_id, "document_id")
        self._validate_path_segment(document_version_id, "document_version_id")

        if not content:
            raise ValueError("Image content must not be empty")
        if image_index < 1:
            raise ValueError("image_index must be at least 1")

        suffix = self._get_suffix(mime_type)
        image_id = self._create_image_id(
            content,
            document_id,
            document_version_id,
            image_index,
            mime_type,
        )
        assets_directory = self._get_assets_directory(
            document_id,
            document_version_id,
        )
        assets_directory.mkdir(parents=True, exist_ok=True)

        image_path = assets_directory / f"{image_id}{suffix}"
        image_path.write_bytes(content)

        return StoredImageAsset(
            image_id=image_id,
            path=image_path,
            image_index=image_index,
            mime_type=mime_type,
        )

    def find(
        self,
        document_id: str,
        document_version_id: str,
        image_id: str,
    ) -> Path | None:
        """使用受控标识查找图片，不接受客户端文件路径。 / Finds an image by controlled identifiers without accepting a client file path."""

        # 输入：文档 ID、版本 ID 和系统生成的 image_id。
        # 输出：存在时返回内部 Path，不存在时返回 None。
        self._validate_path_segment(document_id, "document_id")
        self._validate_path_segment(document_version_id, "document_version_id")
        self._validate_image_id(image_id)

        assets_directory = self._get_assets_directory(
            document_id,
            document_version_id,
        )
        for suffix in self._MIME_TYPE_SUFFIXES.values():
            candidate = assets_directory / f"{image_id}{suffix}"
            if candidate.is_file():
                return candidate
        return None

    def read(
        self,
        document_id: str,
        document_version_id: str,
        image_id: str,
    ) -> bytes:
        """按 image_id 读取图片字节，不存在时明确失败。 / Reads image bytes by image ID and fails explicitly when missing."""

        image_path = self.find(document_id, document_version_id, image_id)
        if image_path is None:
            raise FileNotFoundError(f"Image asset not found: {image_id}")
        return image_path.read_bytes()

    def delete(
        self,
        document_id: str,
        document_version_id: str,
        image_id: str,
    ) -> bool:
        """删除指定图片，并返回是否确实删除了文件。 / Deletes an image and reports whether a file was actually removed."""

        image_path = self.find(document_id, document_version_id, image_id)
        if image_path is None:
            return False
        image_path.unlink()
        return True

    @classmethod
    def _get_suffix(cls, mime_type: str) -> str:
        """把允许的 MIME 类型转换为安全扩展名。 / Converts an allowed MIME type to a safe file suffix."""

        suffix = cls._MIME_TYPE_SUFFIXES.get(mime_type)
        if suffix is None:
            raise ValueError(f"Unsupported image MIME type: {mime_type}")
        return suffix

    @staticmethod
    def _create_image_id(
        content: bytes,
        document_id: str,
        document_version_id: str,
        image_index: int,
        mime_type: str,
    ) -> str:
        """根据图片内容与来源生成可重复计算的稳定标识。 / Creates a repeatable stable ID from image content and source identity."""

        content_hash = hashlib.sha256(content).hexdigest()
        identity = (
            f"{document_id}|{document_version_id}|{image_index}|"
            f"{mime_type}|{content_hash}"
        )
        identity_bytes = identity.encode("utf-8")
        image_hash = hashlib.sha256(identity_bytes).hexdigest()
        return f"img_{image_hash}"

    def _get_assets_directory(
        self,
        document_id: str,
        document_version_id: str,
    ) -> Path:
        """集中生成内部 assets 目录，调用方不需要拼接路径。 / Builds the internal assets directory so callers do not concatenate paths."""

        document_directory = self._root / document_id
        version_directory = document_directory / document_version_id
        return version_directory / "assets"

    @classmethod
    def _validate_path_segment(cls, value: str, field_name: str) -> None:
        """拒绝包含目录跳转字符的文档标识。 / Rejects document identifiers containing path traversal characters."""

        if cls._SAFE_PATH_SEGMENT.fullmatch(value) is None:
            raise ValueError(f"Invalid {field_name}")

    @classmethod
    def _validate_image_id(cls, image_id: str) -> None:
        """只允许读取由本组件生成的 image_id。 / Allows only image IDs generated by this component."""

        if cls._SAFE_IMAGE_ID.fullmatch(image_id) is None:
            raise ValueError("Invalid image_id")
