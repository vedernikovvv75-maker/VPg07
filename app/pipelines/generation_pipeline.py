from __future__ import annotations

import logging
from typing import Any

from haystack import Pipeline
from haystack.components.embedders import OpenAITextEmbedder
from haystack.utils import Secret

from app.config import Settings
from app.llm.generator import create_generator
from app.llm.prompt_builder import create_prompt_builder
from app.schemas import AnswerResult, RetrievedChunk
from app.vectorstore.pinecone_client import PineconeClient
from app.vectorstore.pinecone_retriever import PineconeRetriever

logger = logging.getLogger(__name__)


def _create_text_embedder(settings: Settings) -> OpenAITextEmbedder:
  if not settings.proxyapi_key:
    raise ValueError("PROXYAPI_KEY is required for query embeddings")

  kwargs: dict[str, Any] = {
    "model": settings.openai_embedding_model,
    "api_key": Secret.from_token(settings.proxyapi_key),
    "dimensions": settings.embedding_dimension,
  }
  if settings.proxyapi_base_url:
    kwargs["api_base_url"] = settings.proxyapi_base_url
  return OpenAITextEmbedder(**kwargs)


def build_haystack_generation_pipeline(
  settings: Settings,
  pinecone_client: PineconeClient,
  *,
  top_k: int = 5,
) -> Pipeline:
  """Internal Haystack Pipeline: TextEmbedder -> Retriever -> PromptBuilder -> Generator."""
  text_embedder = _create_text_embedder(settings)
  retriever = PineconeRetriever(pinecone_client=pinecone_client, top_k=top_k)
  prompt_builder = create_prompt_builder()
  generator = create_generator(settings)

  pipeline = Pipeline()
  pipeline.add_component("text_embedder", text_embedder)
  pipeline.add_component("retriever", retriever)
  pipeline.add_component("prompt_builder", prompt_builder)
  pipeline.add_component("llm", generator)

  pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
  pipeline.connect("retriever.documents", "prompt_builder.documents")
  pipeline.connect("prompt_builder.prompt", "llm.messages")
  return pipeline


class GenerationPipeline:
  """
  Orchestrates user Q&A only.

  Question -> Query Embedding -> Retriever -> PromptBuilder -> Generator -> Answer
  """

  def __init__(self, haystack_pipeline: Pipeline) -> None:
    self._pipeline = haystack_pipeline

  @classmethod
  def create(
    cls,
    settings: Settings,
    pinecone_client: PineconeClient,
    *,
    top_k: int = 5,
  ) -> GenerationPipeline:
    return cls(build_haystack_generation_pipeline(settings, pinecone_client, top_k=top_k))

  def answer(self, question: str, user_id: str | None = None) -> AnswerResult:
    question = question.strip()
    if not question:
      raise ValueError("question must not be empty")

    logger.info("GenerationPipeline: question=%r user_id=%r", question, user_id)

    run_input: dict[str, dict[str, Any]] = {
      "text_embedder": {"text": question},
      "prompt_builder": {"query": question},
    }
    if user_id:
      run_input["retriever"] = {"filters": {"user_id": {"$eq": user_id}}}

    result = self._pipeline.run(
      run_input,
      include_outputs_from={"retriever"},
    )

    replies = result.get("llm", {}).get("replies", [])
    answer_text = "Не удалось сформировать ответ."
    if replies:
      text = replies[0].text if hasattr(replies[0], "text") else str(replies[0])
      if text:
        answer_text = text

    documents = result.get("retriever", {}).get("documents", [])
    sources: list[RetrievedChunk] = []
    for doc in documents:
      meta = doc.meta or {}
      sources.append(
        RetrievedChunk(
          text=doc.content or "",
          score=float(doc.score or meta.get("score") or 0.0),
          file_name=meta.get("file_name"),
          page=meta.get("page"),
          chunk_id=meta.get("chunk_id"),
          document_id=meta.get("document_id"),
        )
      )

    logger.info("GenerationPipeline: answer ready (%d source(s))", len(sources))
    return AnswerResult(answer=answer_text, sources=sources)
