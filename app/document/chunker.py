from __future__ import annotations

import logging
import re

from app.schemas import Chunk, StructuredDocument
from app.document.text_export import is_boilerplate_chunk

logger = logging.getLogger(__name__)

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MARKDOWN_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_LETTER_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")


class Chunker:
  """Splits a structured document into text chunks. No embedding or storage logic."""

  def __init__(
    self,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    min_chunk_chars: int = 80,
    min_letter_ratio: float = 0.35,
  ) -> None:
    self._chunk_size = chunk_size
    self._chunk_overlap = chunk_overlap
    self._min_chunk_chars = min_chunk_chars
    self._min_letter_ratio = min_letter_ratio

  def chunk(self, document: StructuredDocument) -> list[Chunk]:
    text = self._normalize_text(document.raw_markdown or "")
    if not text:
      logger.warning("Chunker: empty document %s", document.file_name)
      return []

    sections = self._split_into_sections(text)
    raw_segments: list[str] = []

    for section in sections:
      raw_segments.extend(self._chunk_section(section))

    filtered = [
      segment
      for segment in raw_segments
      if self._is_usable_chunk(segment) and not is_boilerplate_chunk(segment)
    ]
    if not filtered and raw_segments:
      non_boilerplate = [s for s in raw_segments if not is_boilerplate_chunk(s)]
      pool = non_boilerplate or raw_segments
      logger.warning(
        "Chunker: segments filtered for %s, keeping %d longest segment(s) as fallback",
        document.file_name,
        min(3, len(pool)),
      )
      pool.sort(key=len, reverse=True)
      filtered = pool[:3]

    chunks: list[Chunk] = []
    for idx, content in enumerate(filtered):
      chunks.append(
        Chunk(
          content=content,
          page=None,
          chunk_id=idx,
          metadata={"file_name": document.file_name, "document_id": document.document_id},
        )
      )

    logger.info(
      "Chunker: produced %d usable chunks for %s (from %d raw segments)",
      len(chunks),
      document.file_name,
      len(raw_segments),
    )
    return chunks

  def _normalize_text(self, text: str) -> str:
    text = _HTML_COMMENT_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line and not self._is_noise_line(line)]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

  def _is_noise_line(self, line: str) -> bool:
    if len(line) < 3:
      return True
    letters = len(_LETTER_RE.findall(line))
    if letters == 0:
      return True
    return letters / max(len(line), 1) < 0.2

  def _split_into_sections(self, text: str) -> list[str]:
    matches = list(_MARKDOWN_HEADER_RE.finditer(text))
    if not matches:
      return [text]

    sections: list[str] = []
    prefix = text[: matches[0].start()].strip()
    if prefix:
      sections.append(prefix)

    for index, match in enumerate(matches):
      header = match.group(2).strip()
      body_start = match.end()
      body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
      body = text[body_start:body_end].strip()
      section_text = f"{header}\n{body}".strip() if body else header
      if section_text:
        sections.append(section_text)

    return sections or [text]

  def _chunk_section(self, section: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section) if p.strip()]
    segments: list[str] = []
    buffer = ""

    for paragraph in paragraphs:
      units = self._split_paragraph_units(paragraph)
      for unit in units:
        candidate = f"{buffer}\n\n{unit}".strip() if buffer else unit
        if len(candidate) <= self._chunk_size:
          buffer = candidate
          continue
        if buffer:
          segments.append(buffer)
        if len(unit) <= self._chunk_size:
          buffer = unit
        else:
          segments.extend(self._split_long_text(unit))
          buffer = ""

    if buffer:
      segments.append(buffer)
    return segments

  def _split_paragraph_units(self, paragraph: str) -> list[str]:
    if len(paragraph) <= self._chunk_size:
      return [paragraph]
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(paragraph) if s.strip()]
    return sentences or [paragraph]

  def _split_long_text(self, text: str) -> list[str]:
    segments: list[str] = []
    start = 0
    while start < len(text):
      end = min(start + self._chunk_size, len(text))
      if end < len(text):
        split_at = text.rfind(" ", start, end)
        if split_at > start + self._chunk_size // 2:
          end = split_at
      segment = text[start:end].strip()
      if segment:
        segments.append(segment)
      if end >= len(text):
        break
      start = max(end - self._chunk_overlap, start + 1)
    return segments

  def _is_usable_chunk(self, text: str) -> bool:
    if len(text) < self._min_chunk_chars:
      return False
    letters = len(_LETTER_RE.findall(text))
    return letters / max(len(text), 1) >= self._min_letter_ratio
