from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

import requests
from telegram import Bot
from telegram._files.file import is_local_file

from telegram_proxy import normalize_proxy_url

logger = logging.getLogger(__name__)


async def download_telegram_document(
  bot: Bot,
  file_id: str,
  dest_path: Path,
  proxy_url: str | None,
  timeouts: dict[str, int],
) -> int:
  dest_path.parent.mkdir(parents=True, exist_ok=True)
  tg_file = await bot.get_file(file_id, **timeouts)

  if not tg_file.file_path:
    raise RuntimeError("Telegram API не вернул file_path")

  if is_local_file(tg_file.file_path):
    shutil.copy2(tg_file.file_path, dest_path)
    return dest_path.stat().st_size

  try:
    await tg_file.download_to_drive(custom_path=str(dest_path), **timeouts)
    if dest_path.is_file() and dest_path.stat().st_size > 0:
      size = dest_path.stat().st_size
      logger.info("File downloaded via PTB: %d bytes", size)
      return size
  except Exception:
    logger.warning("PTB download failed, retrying via requests+proxy", exc_info=True)

  base_url = str(bot.base_url).rstrip("/")
  file_path = tg_file.file_path.lstrip("/")
  url = f"{base_url}/file/bot{bot.token}/{file_path}"

  proxy = normalize_proxy_url(proxy_url) if proxy_url else None
  proxies = {"http": proxy, "https": proxy} if proxy else None
  timeout = timeouts.get("read_timeout", 300)

  def _fetch() -> bytes:
    response = requests.get(url, proxies=proxies, timeout=timeout)
    response.raise_for_status()
    return response.content

  content = await asyncio.to_thread(_fetch)
  if not content:
    raise RuntimeError("Пустой ответ при скачивании файла")
  dest_path.write_bytes(content)
  logger.info("File downloaded via requests: %d bytes", len(content))
  return len(content)
