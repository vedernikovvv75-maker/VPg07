from __future__ import annotations

import logging

from openai import OpenAI

from app.config import Settings

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM = (
  "Ты помощник. Составь ровно одно короткое предложение на русском языке, "
  "которое кратко описывает содержание документа. "
  "Текст мог быть извлечён с ошибками OCR — восстанавливай общий смысл. "
  "Без списков и без вводных фраз."
)


class SummaryGenerator:
  """Generates a one-sentence summary after document ingestion. Used only in IngestionPipeline."""

  def __init__(self, settings: Settings) -> None:
    if not settings.proxyapi_key:
      raise ValueError("PROXYAPI_KEY is required for summary generation")

    client_kwargs: dict[str, str | float] = {
      "api_key": settings.proxyapi_key,
      "timeout": settings.api_timeout,
      "max_retries": settings.api_max_retries,
    }
    if settings.proxyapi_base_url:
      client_kwargs["base_url"] = settings.proxyapi_base_url
    self._client = OpenAI(**client_kwargs)
    self._model = settings.openai_chat_model

  def summarize(self, file_name: str, chunk_texts: list[str]) -> str:
    if not chunk_texts:
      return f"Документ «{file_name}» обработан, но текст для резюме не найден."

    preview = "\n\n".join(chunk_texts[:5])
    if len(preview) > 6000:
      preview = preview[:6000]

    logger.info("SummaryGenerator: summarizing %s", file_name)
    response = self._client.chat.completions.create(
      model=self._model,
      temperature=0.2,
      messages=[
        {"role": "system", "content": SUMMARY_SYSTEM},
        {
          "role": "user",
          "content": f"Имя файла: {file_name}\n\nФрагменты документа:\n{preview}",
        },
      ],
    )
    content = response.choices[0].message.content or ""
    summary = content.strip().split("\n")[0].strip()
    return summary or f"Документ «{file_name}» успешно проиндексирован."
