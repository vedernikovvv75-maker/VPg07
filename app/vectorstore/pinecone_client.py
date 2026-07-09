from __future__ import annotations

import logging
from typing import Any

from pinecone import Pinecone

from app.config import Settings
from app.schemas import ChunkMetadata, RetrievedChunk

logger = logging.getLogger(__name__)


class PineconeClient:
  """Encapsulates Pinecone upsert and search. No Docling or LLM logic."""

  def __init__(self, settings: Settings, namespace: str = "") -> None:
    if not settings.pinecone_api_key:
      raise ValueError("PINECONE_API_KEY is required")
    if not settings.pinecone_index_name and not settings.pinecone_host:
      raise ValueError("PINECONE_INDEX_NAME or PINECONE_HOST is required")

    self._namespace = namespace
    pc = Pinecone(api_key=settings.pinecone_api_key)
    if settings.pinecone_host:
      self._index = pc.Index(host=settings.pinecone_host)
    else:
      self._index = pc.Index(settings.pinecone_index_name)

  def upsert_chunks(
    self,
    vectors: list[list[float]],
    metadata_list: list[ChunkMetadata],
  ) -> int:
    if len(vectors) != len(metadata_list):
      raise ValueError("vectors and metadata_list must have the same length")
    if not vectors:
      return 0

    payload: list[dict[str, Any]] = []
    for vector, meta in zip(vectors, metadata_list):
      vector_id = f"{meta.document_id}-{meta.chunk_id}"
      pine_meta = meta.model_dump(exclude_none=True)
      if meta.page is None:
        pine_meta.pop("page", None)
      payload.append({"id": vector_id, "values": vector, "metadata": pine_meta})

    batch_size = 100
    for start in range(0, len(payload), batch_size):
      batch = payload[start : start + batch_size]
      self._index.upsert(vectors=batch, namespace=self._namespace)

    logger.info("Pinecone: upserted %d vectors (namespace=%r)", len(payload), self._namespace)
    return len(payload)

  def search(
    self,
    query_vector: list[float],
    top_k: int = 5,
    filters: dict | None = None,
  ) -> list[RetrievedChunk]:
    query_kwargs: dict[str, Any] = {
      "vector": query_vector,
      "top_k": top_k,
      "include_metadata": True,
      "namespace": self._namespace,
    }
    if filters:
      query_kwargs["filter"] = filters

    response = self._index.query(**query_kwargs)
    matches = response.get("matches", []) if isinstance(response, dict) else response.matches

    results: list[RetrievedChunk] = []
    for match in matches:
      meta = match.get("metadata", {}) if isinstance(match, dict) else (match.metadata or {})
      results.append(
        RetrievedChunk(
          text=str(meta.get("text", "")),
          score=float(match.get("score", 0) if isinstance(match, dict) else match.score or 0),
          file_name=meta.get("file_name"),
          page=meta.get("page"),
          chunk_id=meta.get("chunk_id"),
          document_id=meta.get("document_id"),
        )
      )
    return results

  def delete_by_document_id(self, document_id: str) -> None:
    self._index.delete(filter={"document_id": {"$eq": document_id}}, namespace=self._namespace)
    logger.info("Pinecone: deleted vectors for document_id=%s", document_id)

  @property
  def namespace(self) -> str:
    return self._namespace

  def describe_namespace_stats(self) -> dict[str, int]:
    stats = self._index.describe_index_stats()
    namespaces = stats.get("namespaces", {}) if isinstance(stats, dict) else stats.namespaces
    namespace_stats = namespaces.get(self._namespace, {}) if isinstance(namespaces, dict) else {}
    vector_count = (
      namespace_stats.get("vector_count", 0)
      if isinstance(namespace_stats, dict)
      else getattr(namespace_stats, "vector_count", 0)
    )
    return {"vector_count": int(vector_count or 0)}

  def clear_namespace(self) -> int:
    before = self.describe_namespace_stats()["vector_count"]
    if before == 0:
      logger.info("Pinecone: namespace %r is already empty", self._namespace)
      return 0

    self._index.delete(delete_all=True, namespace=self._namespace)
    logger.info("Pinecone: cleared namespace %r (%d vectors)", self._namespace, before)
    return before
