from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Metadata stored alongside each vector in Pinecone."""

    text: str
    file_name: str
    page: int | None = None
    chunk_id: int
    created_at: str
    document_id: str
    user_id: str | None = None
    namespace: str | None = None
    company_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class Chunk(BaseModel):
    """A text segment produced by the chunker."""

    content: str
    page: int | None = None
    chunk_id: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructuredDocument(BaseModel):
    """Result of Docling conversion before chunking."""

    file_name: str
    document_id: str
    raw_markdown: str | None = None
    pages_count: int | None = None


class IngestionResult(BaseModel):
    """Returned by IngestionPipeline after successful document processing."""

    document_id: str
    file_name: str
    chunks_count: int
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RetrievedChunk(BaseModel):
    """A chunk returned by the retriever during generation."""

    text: str
    score: float
    file_name: str | None = None
    page: int | None = None
    chunk_id: int | None = None
    document_id: str | None = None


class AnswerResult(BaseModel):
    """Returned by GenerationPipeline after answering a user question."""

    answer: str
    sources: list[RetrievedChunk] = Field(default_factory=list)
