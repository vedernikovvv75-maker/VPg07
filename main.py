"""
Application entry point.

All dependencies are created here and passed via constructors.
No global PineconeClient, OpenAI, or Haystack Pipeline instances in other modules.
"""

from __future__ import annotations

import logging

from app.logging_config import setup_logging
from app.bot.handlers import BotHandlers
from app.bot.telegram_app import run_bot
from app.config import Settings
from app.document.chunker import Chunker
from app.document.docling_processor import DoclingProcessor
from app.embeddings.embedder import OpenAIEmbedder
from app.llm.summary_generator import SummaryGenerator
from app.pipelines.generation_pipeline import GenerationPipeline
from app.pipelines.ingestion_pipeline import IngestionPipeline
from app.settings_validation import validate_settings
from app.vectorstore.pinecone_client import PineconeClient

logger = logging.getLogger(__name__)


def build_ingestion_pipeline(
  settings: Settings,
  pinecone_client: PineconeClient | None = None,
) -> IngestionPipeline:
  client = pinecone_client or PineconeClient(settings, namespace=settings.pinecone_namespace)
  return IngestionPipeline(
    docling_processor=DoclingProcessor(settings),
    chunker=Chunker(
      chunk_size=settings.chunk_size,
      chunk_overlap=settings.chunk_overlap,
      min_chunk_chars=settings.min_chunk_chars,
    ),
    embedder=OpenAIEmbedder(settings),
    pinecone_client=client,
    summary_generator=SummaryGenerator(settings),
  )


def build_generation_pipeline(settings: Settings, pinecone_client: PineconeClient) -> GenerationPipeline:
  return GenerationPipeline.create(
    settings,
    pinecone_client,
    top_k=settings.generation_top_k,
  )


def build_app(settings: Settings | None = None) -> BotHandlers:
  cfg = settings or Settings.from_env()
  pinecone_client = PineconeClient(cfg, namespace=cfg.pinecone_namespace)

  return BotHandlers(
    ingestion_pipeline=build_ingestion_pipeline(cfg, pinecone_client),
    generation_pipeline=build_generation_pipeline(cfg, pinecone_client),
  )


def main() -> None:
  settings = Settings.from_env()
  setup_logging(settings.log_level)

  config_errors = validate_settings(settings, for_bot=True)
  if config_errors:
    for error in config_errors:
      logger.error("Config: %s", error)
    raise SystemExit("Fix .env (see EnvExample) and run: python scripts/check_env.py")

  from telegram_proxy import configure_telegram_proxy, resolve_proxy_url
  from tor_launcher import start_tor_if_needed

  proxy_url = resolve_proxy_url()
  start_tor_if_needed(proxy_url)
  effective_proxy = configure_telegram_proxy()

  logger.info("Telegram polling starts immediately; RAG pipelines init on first message.")
  run_bot(settings.telegram_bot_token, settings, proxy_url=effective_proxy)


if __name__ == "__main__":
  main()
