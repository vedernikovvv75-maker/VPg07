from __future__ import annotations

from haystack.components.builders import PromptBuilder

RAG_TEMPLATE = """\
Ты помощник по документам. Отвечай на вопрос пользователя, опираясь на контекст ниже.
Текст мог быть извлечён из PDF с ошибками OCR — восстанавливай смысл по контексту.
Отвечай по-русски, кратко и по делу. Не выдумывай факты, которых нет в контексте.
Если ответ неполный, сформулируй его из доступных фрагментов и укажи, что деталей в документе нет.

Контекст:
{% for document in documents %}
- {{ document.content }}
{% endfor %}

Вопрос: {{ query }}
Ответ:"""


def create_prompt_builder() -> PromptBuilder:
  """Haystack PromptBuilder for RAG."""
  return PromptBuilder(
    template=RAG_TEMPLATE,
    required_variables=["documents", "query"],
  )
