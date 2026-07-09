"""Clear all vectors in the configured Pinecone namespace."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.vectorstore.pinecone_client import PineconeClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
  parser = argparse.ArgumentParser(description="Delete all vectors in a Pinecone namespace")
  parser.add_argument(
    "--namespace",
    type=str,
    default=None,
    help="Override PINECONE_NAMESPACE from .env",
  )
  parser.add_argument(
    "--force",
    action="store_true",
    help="Skip confirmation prompt",
  )
  args = parser.parse_args()

  settings = Settings.from_env()
  namespace = args.namespace if args.namespace is not None else settings.pinecone_namespace
  client = PineconeClient(settings, namespace=namespace)

  stats = client.describe_namespace_stats()
  vector_count = stats["vector_count"]
  print(f"Namespace: {namespace!r}")
  print(f"Vectors:   {vector_count}")

  if vector_count == 0:
    print("Nothing to delete.")
    return

  if not args.force:
    answer = input(f"Delete all {vector_count} vectors in {namespace!r}? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
      print("Cancelled.")
      return

  deleted = client.clear_namespace()
  print(f"Deleted {deleted} vectors from namespace {namespace!r}.")


if __name__ == "__main__":
  main()
