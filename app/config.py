from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
  telegram_bot_token: str
  proxyapi_key: str
  proxyapi_base_url: str
  openai_embedding_model: str
  openai_chat_model: str
  embedding_dimension: int
  pinecone_api_key: str
  pinecone_index_name: str
  pinecone_host: str | None
  pinecone_namespace: str
  chunk_size: int
  chunk_overlap: int
  min_chunk_chars: int
  log_level: str
  api_timeout: float
  api_max_retries: int
  generation_top_k: int
  docling_page_range: str | None
  docling_images_scale: float
  docling_do_table_structure: bool
  docling_do_ocr: bool

  @classmethod
  def from_env(cls) -> Settings:
    proxyapi_key = os.getenv("PROXYAPI_KEY") or os.getenv("OPENAI_API_KEY", "")
    proxyapi_base_url = (
      os.getenv("PROXYAPI_BASE_URL")
      or os.getenv("OPENAI_BASE_URL")
      or "https://api.proxyapi.ru/openai/v1"
    )
    return cls(
      telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
      proxyapi_key=proxyapi_key,
      proxyapi_base_url=proxyapi_base_url,
      openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
      openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
      embedding_dimension=int(os.getenv("OPENAI_EMBEDDING_DIMENSION", "512")),
      pinecone_api_key=os.getenv("PINECONE_API_KEY", ""),
      pinecone_index_name=os.getenv("PINECONE_INDEX_NAME", ""),
      pinecone_host=os.getenv("PINECONE_HOST"),
      pinecone_namespace=os.getenv("PINECONE_NAMESPACE", "vpg07"),
      chunk_size=int(os.getenv("CHUNK_SIZE", "800")),
      chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "120")),
      min_chunk_chars=int(os.getenv("MIN_CHUNK_CHARS", "80")),
      log_level=os.getenv("LOG_LEVEL", "INFO"),
      api_timeout=float(os.getenv("API_TIMEOUT", "60")),
      api_max_retries=int(os.getenv("API_MAX_RETRIES", "3")),
      generation_top_k=int(os.getenv("GENERATION_TOP_K", "5")),
      docling_page_range=os.getenv("DOCLING_PAGE_RANGE") or None,
      docling_images_scale=float(os.getenv("DOCLING_IMAGES_SCALE", "0.75")),
      docling_do_table_structure=os.getenv("DOCLING_TABLE_STRUCTURE", "false").strip().lower()
      in {"1", "true", "yes", "on"},
      docling_do_ocr=os.getenv("DOCLING_DO_OCR", "true").strip().lower() in {"1", "true", "yes", "on"},
    )
