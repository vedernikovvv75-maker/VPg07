from __future__ import annotations


def parse_page_range(raw: str | None) -> tuple[int, int] | None:
  """Parse '6-17' or '6' into Docling 1-based page range."""
  if not raw or not raw.strip():
    return None

  text = raw.strip()
  if "-" in text:
    start_str, end_str = text.split("-", 1)
    start, end = int(start_str.strip()), int(end_str.strip())
  else:
    start = end = int(text)

  if start < 1 or end < start:
    raise ValueError(f"Invalid page range {raw!r}. Use START-END (e.g. 6-17), pages start at 1.")
  return start, end
