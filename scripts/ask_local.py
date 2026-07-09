"""Local Q&A test: embed query -> Pinecone retrieval -> LLM answer."""

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
from app.pipelines.generation_pipeline import GenerationPipeline
from app.settings_validation import validate_settings
from app.vectorstore.pinecone_client import PineconeClient

logger = logging.getLogger(__name__)


def _safe_print(text: str) -> None:
  try:
    print(text)
  except UnicodeEncodeError:
    print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
      sys.stdout.encoding or "utf-8", errors="replace"
    ))


def main() -> None:
  parser = argparse.ArgumentParser(description="Ask a question against indexed documents")
  parser.add_argument("question", nargs="+", help="Question text")
  parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve")
  args = parser.parse_args()

  question = " ".join(args.question).strip()
  settings = Settings.from_env()
  setup_logging(settings.log_level)

  errors = validate_settings(settings)
  if errors:
    for error in errors:
      logger.error("%s", error)
    raise SystemExit(1)

  pinecone = PineconeClient(settings, namespace=settings.pinecone_namespace)
  pipeline = GenerationPipeline.create(settings, pinecone, top_k=args.top_k)

  logger.info("Asking: %s", question)
  result = pipeline.answer(question)

  print("\n--- Answer ---")
  _safe_print(result.answer)

  if result.sources:
    print("\n--- Sources ---")
    for idx, source in enumerate(result.sources, start=1):
      label = source.file_name or source.document_id or f"chunk-{idx}"
      print(f"{idx}. [{source.score:.3f}] {label}")
      snippet = source.text[:200] + ("..." if len(source.text) > 200 else "")
      _safe_print(f"   {snippet}")


if __name__ == "__main__":
  main()
