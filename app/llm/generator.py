from __future__ import annotations

from typing import Any

from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.utils import Secret

from app.config import Settings


def create_generator(settings: Settings) -> OpenAIChatGenerator:
  """Haystack OpenAIChatGenerator configured for ProxyAPI."""
  if not settings.proxyapi_key:
    raise ValueError("PROXYAPI_KEY is required for generation")

  kwargs: dict[str, Any] = {
    "model": settings.openai_chat_model,
    "api_key": Secret.from_token(settings.proxyapi_key),
    "generation_kwargs": {"temperature": 0.2},
    "timeout": settings.api_timeout,
    "max_retries": settings.api_max_retries,
  }
  if settings.proxyapi_base_url:
    kwargs["api_base_url"] = settings.proxyapi_base_url
  return OpenAIChatGenerator(**kwargs)
