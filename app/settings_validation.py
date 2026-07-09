from __future__ import annotations

from app.config import Settings


def validate_settings(settings: Settings, *, for_bot: bool = False) -> list[str]:
  """Return list of missing or invalid configuration fields."""
  errors: list[str] = []

  if for_bot and not settings.telegram_bot_token:
    errors.append("TELEGRAM_BOT_TOKEN is required for the bot")

  if not settings.proxyapi_key:
    errors.append("PROXYAPI_KEY (or OPENAI_API_KEY) is required for embeddings and LLM")

  if not settings.pinecone_api_key:
    errors.append("PINECONE_API_KEY is required")

  if not settings.pinecone_index_name and not settings.pinecone_host:
    errors.append("PINECONE_INDEX_NAME or PINECONE_HOST is required")

  if settings.embedding_dimension <= 0:
    errors.append("OPENAI_EMBEDDING_DIMENSION must be positive")

  if settings.chunk_size <= 0:
    errors.append("CHUNK_SIZE must be positive")

  return errors
