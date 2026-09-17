from pathlib import Path
import logging
from typing import Protocol

from PIL import Image

from app.document_processing.excel_parser import ExcelDocumentParser
from app.document_processing.pdf_parser import PdfDocumentParser
from app.schemas.document import ParsedBlock
from app.document_processing.excel_image_extractor import ExcelImageExtractor
from app.document_processing.storage import LocalImageAssetStorage, StoredImageAsset
from app.document_processing.pdf_renderer import PyMuPdfPageRenderer
from app.services.ocr_service import OcrProvider
from app.services.vision_service import VisionBlockService, VisionContext, VisionProvider

_LOGGER = logging.getLogger(__name__)


class DocumentParser(Protocol):
    """定义原始文档转换为带定位语义块的接口。 / Defines the interface for converting an original document into located semantic blocks."""

    def parse(self, path: Path) -> list[ParsedBlock]:
        """解析指定本地文档。 / Parses the specified local document.

        参数说明 / Args:
            path: 需要解析的本地文件路径；具体实现根据文件内容生成 ParsedBlock。
        """

        ...


class DocumentParserRegistry:
    """根据扩展名选择受支持的本地文档解析器。 / Selects a supported local document parser by file extension."""

    def __init__(self, image_storage: LocalImageAssetStorage | None = None,
                 vision_provider: VisionProvider | None = None,
                 ocr_provider: OcrProvider | None = None,
                 image_mode: str = "off") -> None:
        """注册 v1 支持的 PDF 和 Excel 解析器。 / Registers the PDF and Excel parsers supported in v1.

        参数说明 / Args:
            image_storage: 图片资产存储；启用 OCR/Vision 时用于保存提取出的图片。
            vision_provider: 图片理解服务；image_mode=vision 时必须提供。
            ocr_provider: 文字识别服务；PDF OCR 或 image_mode=ocr 时使用。
            image_mode: Excel 图片处理方式，可选 off、vision 或 ocr。
        """

        if image_mode not in ("off", "vision", "ocr"):
            raise ValueError("image_mode must be off, vision or ocr")
        if image_mode != "off" and image_storage is None:
            raise ValueError("image_storage is required")
        if image_mode == "vision" and vision_provider is None:
            raise ValueError("vision_provider is required")
        if image_mode == "ocr" and ocr_provider is None:
            raise ValueError("ocr_provider is required")
        self._image_storage = image_storage
        self._vision_provider = vision_provider
        self._ocr_provider = ocr_provider
        self._image_mode = image_mode
        pdf_parser = PdfDocumentParser()
        if ocr_provider is not None:
            if image_storage is None:
                raise ValueError("image_storage is required for PDF OCR")
            pdf_parser = PdfDocumentParser(
                ocr_provider=ocr_provider, image_storage=image_storage,
                page_renderer=PyMuPdfPageRenderer(),
            )
        self._pdf_parser = pdf_parser
        excel_parser = ExcelDocumentParser()
        self._parsers: dict[str, DocumentParser] = {
            ".pdf": pdf_parser,
            ".xlsx": excel_parser,
            ".xlsm": excel_parser,
        }

    def get(self, path: Path) -> DocumentParser:
        """返回对应解析器，不支持的格式会明确失败。 / Returns the matching parser and explicitly fails for unsupported formats.

        参数说明 / Args:
            path: 待解析文件路径；这里主要读取它的后缀来选择 PDF 或 Excel 解析器。
        """

        parser = self._parsers.get(path.suffix.casefold())
        if parser is None:
            raise ValueError(f"Unsupported document format: {path.suffix}")
        return parser

    def parse_document(self, path: Path, document_id: str,
                       document_version_id: str, source_name: str) -> list[ParsedBlock]:
        """解析主文档再补充图片块；单图失败只记录警告。 / Parses text and optional image evidence.

        参数说明 / Args:
            path: 已保存到服务器的正式文档路径。
            document_id: 当前文档编号，保存图片资产时用于确定所属目录。
            document_version_id: 当前版本编号，用于隔离图片、日志和检索版本。
            source_name: 用户上传时的原始文件名，传给 Vision 上下文作为来源信息。
        """
        suffix = path.suffix.casefold()
        parser = self.get(path)
        if suffix == ".pdf":
            return self._pdf_parser.parse(path, document_id, document_version_id)
        blocks = parser.parse(path)
        if self._image_mode == "off":
            return blocks
        extractor = ExcelImageExtractor(self._image_storage)
        images = extractor.extract(path, document_id, document_version_id)
        stats = {"total_images": extractor.total_images,
                 "skipped_images": 0, "ocr_images": 0, "vision_images": 0,
                 "failed_images": extractor.failed_images}
        for image in images:
            try:
                with Image.open(image.image_path) as picture:
                    width, height = picture.size
                if width < 32 or height < 32:
                    stats["skipped_images"] += 1
                    continue
                context = VisionContext(source_name=source_name, sheet=image.sheet,
                                        cell_range=image.cell_range)
                asset = StoredImageAsset(image.image_id, image.image_path,
                                         image.image_index, image.mime_type)
                block = None
                if self._image_mode == "vision":
                    service = VisionBlockService(self._vision_provider)
                    block = service.parse(asset, context)
                else:
                    result = self._ocr_provider.extract_text(asset.path)
                    if result.success and result.text.strip():
                        block = ParsedBlock(content=result.text, modality="image",
                            extraction_method="ocr", image_id=asset.image_id,
                            image_path=asset.path, image_index=asset.image_index,
                            mime_type=asset.mime_type, confidence=result.confidence,
                            sheet=context.sheet, cell_range=context.cell_range)
                if block is None:
                    stats["failed_images"] += 1
                    _LOGGER.warning("image_recognition_failed version=%s image=%s",
                                    document_version_id, image.image_index)
                    continue
                blocks.append(block)
                stats[self._image_mode + "_images"] += 1
            except Exception:
                stats["failed_images"] += 1
                _LOGGER.warning("image_processing_failed version=%s image=%s",
                                document_version_id, image.image_index)
        _LOGGER.info("image_processing_summary version=%s stats=%s", document_version_id, stats)
        return blocks
