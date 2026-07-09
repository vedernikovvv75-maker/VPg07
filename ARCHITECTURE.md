# Architecture

## Principle

Two independent pipelines. **Pipeline orchestrates, components execute.**

```
                DOCUMENT WORLD

PDF/DOCX
   |
DoclingProcessor
   |
Chunker
   |
Embedder
   |
PineconeClient
   |
SummaryGenerator


                QUERY WORLD

User message
   |
GenerationPipeline (may use internal Haystack Pipeline)
   |
Answer
```

External modules (`bot/`, `document/`, `vectorstore/`) must not depend on Haystack API directly.

## Module responsibilities

| Module | Does | Must not |
|--------|------|----------|
| `bot/` | event -> pipeline -> Telegram reply | Docling, Pinecone, Haystack, LLM |
| `pipelines/ingestion_pipeline.py` | orchestrate document ingestion | answer questions, Telegram |
| `pipelines/generation_pipeline.py` | orchestrate Q&A | Docling, Pinecone writes |
| `document/` | Docling, chunking, OCR cleanup, page ranges | embeddings, storage |
| `embeddings/` | `Embedder` interface + impl | pipeline orchestration |
| `vectorstore/` | Pinecone upsert/search | Docling, LLM |
| `llm/` | Generator, SummaryGenerator, PromptBuilder | indexing, retrieval |

## Dependency injection

All dependencies are created in `main.py` and passed via constructors.

Forbidden inside modules:

- global `PineconeClient()`
- global OpenAI clients
- global Haystack `Pipeline`

## Haystack usage

Haystack is an infrastructure library inside RAG components:

- `TextEmbedder`, `Retriever`, `PromptBuilder`, `OpenAIChatGenerator` — inside generation components
- `GenerationPipeline` may encapsulate an internal Haystack Pipeline
- `bot/handlers.py` must never import Haystack

## Pinecone metadata contract

```json
{
  "text": "...",
  "file_name": "...",
  "page": 5,
  "chunk_id": 12,
  "created_at": "...",
  "document_id": "..."
}
```

Future fields: `user_id`, `namespace`, `company_id`, `tags`.

## Homework alignment

**Ingestion Pipeline** (visible in `pipelines/ingestion_pipeline.py`):

```
Document -> Docling -> Chunking -> Embeddings -> Pinecone -> Summary
```

**Generation Pipeline** (visible in `pipelines/generation_pipeline.py`):

```
Question -> Query Embedding -> Retriever -> PromptBuilder -> OpenAIChatGenerator -> Answer
```

Telegram is a thin interface layer only.
