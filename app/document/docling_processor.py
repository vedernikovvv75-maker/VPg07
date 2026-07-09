from __future__ import annotations

import logging
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from app.config import Settings
from app.document.page_range import parse_page_range
from app.document.text_export import clean_academic_markdown, export_body_markdown
from app.schemas import StructuredDocument

logger = logging.getLogger(__name__)


class DoclingProcessor:
  """Converts files to structured documents via Docling. No Pinecone or Telegram logic."""

  def __init__(self, settings: Settings | None = None, *, do_ocr: bool | None = None) -> None:
    cfg = settings or Settings.from_env()
    self._default_page_range = parse_page_range(cfg.docling_page_range)

    use_ocr = cfg.docling_do_ocr if do_ocr is None else do_ocr
    self._do_ocr = use_ocr

    pdf_options = PdfPipelineOptions()
    pdf_options.do_ocr = use_ocr
    pdf_options.do_table_structure = cfg.docling_do_table_structure
    pdf_options.images_scale = cfg.docling_images_scale
    pdf_options.generate_page_images = False
    pdf_options.generate_picture_images = False

    self._converter = DocumentConverter(
      format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
      }
    )

  def process(
    self,
    file_path: str,
    file_name: str,
    document_id: str,
    *,
    page_range: tuple[int, int] | None = None,
  ) -> StructuredDocument:
    path = Path(file_path)
    if not path.is_file():
      raise FileNotFoundError(f"File not found: {file_path}")

    effective_range = page_range or self._default_page_range
    range_label = f"{effective_range[0]}-{effective_range[1]}" if effective_range else "all"
    logger.info(
      "Docling: converting %s (OCR=%s, pages=%s)",
      file_name,
      self._do_ocr,
      range_label,
    )

    convert_kwargs: dict = {}
    if effective_range:
      convert_kwargs["page_range"] = effective_range

    result = self._converter.convert(str(path), **convert_kwargs)
    document = result.document

    markdown = clean_academic_markdown(export_body_markdown(document))
    if len(markdown) < 200:
      logger.warning(
        "Docling: short body text for %s (%d chars), falling back to full markdown",
        file_name,
        len(markdown),
      )
      fallback = clean_academic_markdown(
        document.export_to_markdown(
          traverse_pictures=True,
          image_placeholder="",
          page_no=None,
        )
      )
      if len(fallback) > len(markdown):
        markdown = fallback

    logger.info("Docling: extracted %d chars for %s (pages=%s)", len(markdown), file_name, range_label)

    pages_count: int | None = None
    if effective_range:
      pages_count = effective_range[1] - effective_range[0] + 1
    elif hasattr(document, "pages"):
      pages_count = len(document.pages)

    return StructuredDocument(
      file_name=file_name,
      document_id=document_id,
      raw_markdown=markdown,
      pages_count=pages_count,
    )
