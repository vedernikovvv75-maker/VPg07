from __future__ import annotations

import asyncio
import logging

from app.bot import messages
from app.pipelines.generation_pipeline import GenerationPipeline
from app.pipelines.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger(__name__)


class BotHandlers:
  """
  Thin Telegram interface layer.

  Receives events, delegates to pipelines, sends results. No Docling, Pinecone, Haystack, or LLM logic here.
  """

  def __init__(
    self,
    ingestion_pipeline: IngestionPipeline,
    generation_pipeline: GenerationPipeline,
  ) -> None:
    self._ingestion = ingestion_pipeline
    self._generation = generation_pipeline

  async def on_document(
    self,
    file_path: str,
    file_name: str,
    *,
    user_id: str | None = None,
  ) -> tuple[str, str]:
    """
    Handle uploaded document.

    Returns (status_message, summary_message).
    """
    try:
      result = await asyncio.to_thread(
        self._ingestion.process_file,
        file_path,
        file_name,
        user_id=user_id,
      )
      status = f"Индексировано фрагментов: {result.chunks_count}. document_id: {result.document_id}"
      summary = f"{messages.FILE_READY}\n\n{result.summary}"
      return status, summary
    except Exception:
      logger.exception("Document ingestion failed for %s", file_name)
      return messages.FILE_ERROR, ""

  async def on_message(self, text: str, user_id: str | None = None) -> str:
    """Handle user text question."""
    question = text.strip()
    if not question:
      return messages.EMPTY_QUESTION

    try:
      result = await asyncio.to_thread(self._generation.answer, question, user_id)
      return result.answer
    except Exception:
      logger.exception("Generation failed for user_id=%r", user_id)
      return messages.QUESTION_ERROR
