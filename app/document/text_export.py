from __future__ import annotations

import re

from docling_core.types.doc import ContentLayer, DocItemLabel

_TOC_LINE_RE = re.compile(r"\.{4,}\s*\d+\s*$")
_PAGE_ONLY_RE = re.compile(r"^\|?\s*\d{1,4}\s*\|?$")
_EMAIL_HEAVY_RE = re.compile(r"@[a-z0-9.-]+\.[a-z]{2,}", re.I)

_BODY_EXPORT_LABELS = {
  DocItemLabel.TITLE,
  DocItemLabel.SECTION_HEADER,
  DocItemLabel.PARAGRAPH,
  DocItemLabel.TEXT,
  DocItemLabel.LIST_ITEM,
  DocItemLabel.CAPTION,
  DocItemLabel.FOOTNOTE,
  DocItemLabel.FORMULA,
  DocItemLabel.TABLE,
  DocItemLabel.PICTURE,
  DocItemLabel.HANDWRITTEN_TEXT,
}


def export_body_markdown(document) -> str:
  """Export main article text, skipping TOC/headers and OCR inside pictures."""
  return document.export_to_markdown(
    traverse_pictures=True,
    labels=_BODY_EXPORT_LABELS,
    included_content_layers={ContentLayer.BODY},
    image_placeholder="",
    escape_html=False,
    escape_underscores=False,
    compact_tables=True,
  )


def clean_academic_markdown(text: str) -> str:
  """Remove TOC leaders, isolated page numbers, and publisher boilerplate lines."""
  cleaned_lines: list[str] = []
  for line in text.splitlines():
    stripped = line.strip()
    if not stripped:
      cleaned_lines.append("")
      continue
    if _TOC_LINE_RE.search(stripped):
      continue
    if _PAGE_ONLY_RE.match(stripped):
      continue
    if stripped.count(".") > len(stripped) * 0.35 and len(stripped) < 200:
      continue
    if "http://" in stripped or "https://" in stripped:
      if len(stripped) < 120:
        continue
    cleaned_lines.append(stripped)

  text = "\n".join(cleaned_lines)
  return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_boilerplate_chunk(text: str) -> bool:
  """Detect TOC fragments, page indexes, and publisher contact blocks."""
  if not text.strip():
    return True

  lines = [line.strip() for line in text.splitlines() if line.strip()]
  if not lines:
    return True

  toc_like = sum(1 for line in lines if _TOC_LINE_RE.search(line) or line.count(".") > len(line) * 0.4)
  if toc_like >= 2:
    return True
  if toc_like == 1 and len(text) < 400:
    return True

  if len(text) < 250 and len(_EMAIL_HEAVY_RE.findall(text)) >= 1:
    return True

  page_markers = sum(1 for line in lines if _PAGE_ONLY_RE.match(line))
  if page_markers >= 2 and len(text) < 500:
    return True

  words = re.findall(r"[A-Za-zА-Яа-яЁё]{4,}", text)
  if len(words) < 8 and toc_like >= 1:
    return True

  return False
