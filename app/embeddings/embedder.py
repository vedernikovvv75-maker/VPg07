from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from openai import OpenAI

from app.config import Settings

logger = logging.getLogger(__name__)


@runtime_checkable
class Embedder(Protocol):
  """Interface for text embedding. Pipeline depends on this, not on a specific model."""

  def embed_documents(self, texts: list[str]) -> list[list[float]]:
    ...

  def embed_query(self, text: str) -> list[float]:
    ...


class BaseEmbedder(ABC):
  @abstractmethod
  def embed_documents(self, texts: list[str]) -> list[list[float]]:
    raise NotImplementedError

  @abstractmethod
  def embed_query(self, text: str) -> list[float]:
    raise NotImplementedError


class OpenAIEmbedder(BaseEmbedder):
  """OpenAI embeddings via proxy API. Used for documents and queries."""

  def __init__(self, settings: Settings, embedding_dimension: int | None = None) -> None:
    if not settings.proxyapi_key:
      raise ValueError("PROXYAPI_KEY is required for embeddings")

    self._model = settings.openai_embedding_model
    self._dimension = embedding_dimension or settings.embedding_dimension
    client_kwargs: dict[str, str | float] = {
      "api_key": settings.proxyapi_key,
      "timeout": settings.api_timeout,
      "max_retries": settings.api_max_retries,
    }
    if settings.proxyapi_base_url:
      client_kwargs["base_url"] = settings.proxyapi_base_url
    self._client = OpenAI(**client_kwargs)

  def embed_documents(self, texts: list[str]) -> list[list[float]]:
    if not texts:
      return []
    return self._create_embeddings(texts)

  def embed_query(self, text: str) -> list[float]:
    return self._create_embeddings([text])[0]

  def _create_embeddings(self, texts: list[str]) -> list[list[float]]:
    request_kwargs: dict[str, Any] = {
      "model": self._model,
      "input": texts,
    }
    if "embedding-3" in self._model and self._dimension:
      request_kwargs["dimensions"] = self._dimension

    logger.info("Embedder: creating %d embedding(s) with %s", len(texts), self._model)
    response = self._client.embeddings.create(**request_kwargs)
    return [item.embedding for item in response.data]
