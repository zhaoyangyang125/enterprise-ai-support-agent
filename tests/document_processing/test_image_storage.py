from pathlib import Path

import pytest

from app.document_processing.storage import LocalImageAssetStorage


def test_image_storage_saves_and_reads_asset(tmp_path: Path) -> None:
    """验证图片保存在版本 assets 目录，并可通过 image_id 读取。 / Verifies an image is stored under version assets and readable by image ID."""

    storage = LocalImageAssetStorage(tmp_path / "document_storage")
    image_content = b"fake-png-content"

    asset = storage.store(
        content=image_content,
        document_id="HMI-MANUAL",
        document_version_id="HMI-MANUAL-V1",
        image_index=1,
        mime_type="image/png",
    )

    expected_directory = (
        tmp_path
        / "document_storage"
        / "HMI-MANUAL"
        / "HMI-MANUAL-V1"
        / "assets"
    )
    assert asset.path.parent == expected_directory
    assert asset.path.name == f"{asset.image_id}.png"
    assert asset.path.read_bytes() == image_content
    assert storage.find("HMI-MANUAL", "HMI-MANUAL-V1", asset.image_id) == asset.path
    assert storage.read("HMI-MANUAL", "HMI-MANUAL-V1", asset.image_id) == image_content


def test_image_id_is_stable_for_same_source_and_content(tmp_path: Path) -> None:
    """验证相同来源和内容重复保存时得到相同 image_id。 / Verifies repeated storage of the same source and content produces the same image ID."""

    storage = LocalImageAssetStorage(tmp_path)
    first = storage.store(
        b"same-image",
        "DOC-001",
        "DOC-001-V1",
        1,
        "image/png",
    )
    second = storage.store(
        b"same-image",
        "DOC-001",
        "DOC-001-V1",
        1,
        "image/png",
    )
    different_index = storage.store(
        b"same-image",
        "DOC-001",
        "DOC-001-V1",
        2,
        "image/png",
    )

    assert first.image_id == second.image_id
    assert first.path == second.path
    assert different_index.image_id != first.image_id


def test_image_storage_deletes_asset(tmp_path: Path) -> None:
    """验证删除后不能再找到或读取图片。 / Verifies a deleted image can no longer be found or read."""

    storage = LocalImageAssetStorage(tmp_path)
    asset = storage.store(
        b"temporary-image",
        "DOC-001",
        "DOC-001-V1",
        1,
        "image/jpeg",
    )

    assert storage.delete("DOC-001", "DOC-001-V1", asset.image_id) is True
    assert storage.find("DOC-001", "DOC-001-V1", asset.image_id) is None
    assert storage.delete("DOC-001", "DOC-001-V1", asset.image_id) is False
    with pytest.raises(FileNotFoundError):
        storage.read("DOC-001", "DOC-001-V1", asset.image_id)


def test_image_storage_rejects_unsafe_or_unsupported_input(tmp_path: Path) -> None:
    """验证路径跳转标识、空图片和不支持的 MIME 类型会被拒绝。 / Verifies traversal identifiers, empty content, and unsupported MIME types are rejected."""

    storage = LocalImageAssetStorage(tmp_path)

    with pytest.raises(ValueError, match="Invalid document_id"):
        storage.store(b"image", "../secret", "V1", 1, "image/png")
    with pytest.raises(ValueError, match="must not be empty"):
        storage.store(b"", "DOC-001", "V1", 1, "image/png")
    with pytest.raises(ValueError, match="Unsupported image MIME type"):
        storage.store(b"image", "DOC-001", "V1", 1, "image/svg+xml")
    with pytest.raises(ValueError, match="Invalid image_id"):
        storage.find("DOC-001", "V1", "../../secret.png")
