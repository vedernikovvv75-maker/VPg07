from __future__ import annotations

import logging
from typing import Any

from haystack import Document, component

from app.schemas import RetrievedChunk
from app.vectorstore.pinecone_client import PineconeClient

logger = logging.getLogger(__name__)


@component
class PineconeRetriever:
  """Haystack component: vector search in Pinecone via PineconeClient."""

  def __init__(self, pinecone_client: PineconeClient, top_k: int = 5) -> None:
    self._client = pinecone_client
    self._top_k = top_k

  @component.output_types(documents=list[Document])
  def run(
    self,
    query_embedding: list[float],
    filters: dict[str, Any] | None = None,
  ) -> dict[str, list[Document]]:
    chunks: list[RetrievedChunk] = self._client.search(
      query_vector=query_embedding,
      top_k=self._top_k,
      filters=filters,
    )
    documents = [
      Document(
        content=chunk.text,
        meta={
          "file_name": chunk.file_name,
          "page": chunk.page,
          "chunk_id": chunk.chunk_id,
          "document_id": chunk.document_id,
          "score": chunk.score,
        },
        score=chunk.score,
      )
      for chunk in chunks
      if chunk.text
    ]
    logger.info("PineconeRetriever: found %d document(s)", len(documents))
    return {"documents": documents}
