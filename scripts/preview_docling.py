"""Preview Docling text extraction without Pinecone (debug / homework)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.document.docling_processor import DoclingProcessor
from app.document.page_range import parse_page_range
from app.document.chunker import Chunker
from app.logging_config import setup_logging


def main() -> None:
  parser = argparse.ArgumentParser(description="Preview Docling markdown and chunks for a file")
  parser.add_argument("file", type=Path, help="Path to PDF or other supported file")
  parser.add_argument("--pages", type=str, default=None, help="Page range, e.g. 6-17")
  parser.add_argument("--show-chunks", action="store_true", help="Also print chunk previews")
  args = parser.parse_args()

  file_path = args.file.resolve()
  if not file_path.is_file():
    raise SystemExit(f"File not found: {file_path}")

  settings = Settings.from_env()
  setup_logging(settings.log_level)
  page_range = parse_page_range(args.pages or settings.docling_page_range)

  processor = DoclingProcessor(settings)
  structured = processor.process(
    str(file_path),
    file_path.name,
    document_id="preview",
    page_range=page_range,
  )

  markdown = structured.raw_markdown or ""
  print(f"\n--- Markdown preview ({len(markdown)} chars) ---\n")
  print(markdown[:8000])
  if len(markdown) > 8000:
    print(f"\n... truncated ({len(markdown) - 8000} more chars)")

  if args.show_chunks:
    chunker = Chunker(
      chunk_size=settings.chunk_size,
      chunk_overlap=settings.chunk_overlap,
      min_chunk_chars=settings.min_chunk_chars,
    )
    chunks = chunker.chunk(structured)
    print(f"\n--- Chunks ({len(chunks)}) ---\n")
    for chunk in chunks[:10]:
      preview = chunk.content[:300] + ("..." if len(chunk.content) > 300 else "")
      print(f"[{chunk.chunk_id}] {preview}\n")


if __name__ == "__main__":
  main()
