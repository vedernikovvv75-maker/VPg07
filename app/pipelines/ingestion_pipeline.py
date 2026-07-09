from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.document.chunker import Chunker
from app.document.docling_processor import DoclingProcessor
from app.embeddings.embedder import Embedder
from app.llm.summary_generator import SummaryGenerator
from app.schemas import ChunkMetadata, IngestionResult
from app.vectorstore.pinecone_client import PineconeClient

logger = logging.getLogger(__name__)


class IngestionPipeline:
  """
  Orchestrates document ingestion only.

  Document -> Docling -> Chunking -> Embeddings -> Pinecone -> Summary
  """

  def __init__(
    self,
    docling_processor: DoclingProcessor,
    chunker: Chunker,
    embedder: Embedder,
    pinecone_client: PineconeClient,
    summary_generator: SummaryGenerator,
  ) -> None:
    self._docling = docling_processor
    self._chunker = chunker
    self._embedder = embedder
    self._pinecone = pinecone_client
    self._summary = summary_generator

  def process_file(
    self,
    file_path: str,
    file_name: str,
    *,
    page_range: tuple[int, int] | None = None,
    user_id: str | None = None,
  ) -> IngestionResult:
    document_id = str(uuid.uuid4())
    range_label = f" pages {page_range[0]}-{page_range[1]}" if page_range else ""
    user_label = f" user_id={user_id}" if user_id else ""
    logger.info("IngestionPipeline: start %s (%s)%s%s", file_name, document_id, range_label, user_label)

    structured = self._docling.process(
      file_path,
      file_name,
      document_id,
      page_range=page_range,
    )
    chunks = self._chunker.chunk(structured)
    if not chunks:
      raise ValueError(f"No chunks produced for file: {file_name}")

    texts = [chunk.content for chunk in chunks]
    vectors = self._embedder.embed_documents(texts)
    created_at = datetime.now(UTC).isoformat()

    metadata_list = [
      ChunkMetadata(
        text=chunk.content,
        file_name=file_name,
        page=chunk.page,
        chunk_id=chunk.chunk_id,
        created_at=created_at,
        document_id=document_id,
        user_id=user_id,
      )
      for chunk in chunks
    ]

    saved = self._pinecone.upsert_chunks(vectors, metadata_list)
    summary = self._summary.summarize(file_name, texts)

    logger.info(
      "IngestionPipeline: done %s — %d chunks saved, summary ready",
      file_name,
      saved,
    )
    return IngestionResult(
      document_id=document_id,
      file_name=file_name,
      chunks_count=saved,
      summary=summary,
    )
