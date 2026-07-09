from __future__ import annotations

import logging
import os
import sys

NOISY_LOGGERS = (
  "httpx",
  "httpcore",
  "pinecone",
  "openai",
  "urllib3",
  "haystack.tracing",
  "apscheduler",
)


def setup_logging(level: str | None = None) -> None:
  level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
  log_level = getattr(logging, level_name, logging.INFO)

  logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
  )

  for logger_name in NOISY_LOGGERS:
    logging.getLogger(logger_name).setLevel(logging.WARNING)
