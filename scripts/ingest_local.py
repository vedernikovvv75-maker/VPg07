"""Local ingestion test: Docling -> chunks -> embeddings -> Pinecone -> summary."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.logging_config import setup_logging
from app.settings_validation import validate_settings
from app.document.page_range import parse_page_range
from main import build_ingestion_pipeline

logger = logging.getLogger(__name__)


def main() -> None:
  parser = argparse.ArgumentParser(description="Ingest a local document into Pinecone")
  parser.add_argument("file", type=Path, help="Path to PDF, DOCX, or other supported file")
  parser.add_argument(
    "--name",
    type=str,
    default=None,
    help="Display file name for metadata (default: basename of path)",
  )
  parser.add_argument(
    "--clear-namespace",
    action="store_true",
    help="Delete all vectors in PINECONE_NAMESPACE before ingestion",
  )
  parser.add_argument(
    "--pages",
    type=str,
    default=None,
    help="Page range for PDF, e.g. 6-17 (1-based, inclusive)",
  )
  args = parser.parse_args()

  file_path = args.file.resolve()
  if not file_path.is_file():
    raise SystemExit(f"File not found: {file_path}")

  file_name = args.name or file_path.name
  settings = Settings.from_env()
  setup_logging(settings.log_level)

  errors = validate_settings(settings)
  if errors:
    for error in errors:
      logger.error("%s", error)
    raise SystemExit(1)

  if args.clear_namespace:
    from app.vectorstore.pinecone_client import PineconeClient

    client = PineconeClient(settings, namespace=settings.pinecone_namespace)
    deleted = client.clear_namespace()
    logger.info("Cleared namespace %r (%d vectors)", settings.pinecone_namespace, deleted)

  page_range = parse_page_range(args.pages)

  pipeline = build_ingestion_pipeline(settings)

  logger.info("Starting ingestion for %s", file_name)
  result = pipeline.process_file(str(file_path), file_name, page_range=page_range)

  print("\n--- Ingestion result ---")
  print(f"document_id:  {result.document_id}")
  print(f"file_name:    {result.file_name}")
  print(f"chunks_count: {result.chunks_count}")
  print(f"summary:      {result.summary}")
  print(f"created_at:   {result.created_at.isoformat()}")


if __name__ == "__main__":
  main()
