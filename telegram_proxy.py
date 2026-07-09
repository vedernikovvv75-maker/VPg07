"""Настройка SOCKS5-прокси (Tor) для python-telegram-bot."""

from __future__ import annotations

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

LOCAL_TOR_PROXY = "socks5h://127.0.0.1:9050"
TELEGRAM_PROBE_URL = "https://api.telegram.org/"


def _env_truthy(name: str, default: bool = False) -> bool:
  raw = os.getenv(name)
  if raw is None:
    return default
  return raw.strip().lower() in {"1", "true", "yes", "on"}


def normalize_proxy_url(proxy_url: str) -> str:
  """socks5h — DNS резолвится через Tor."""
  if proxy_url.startswith("socks5://"):
    return "socks5h://" + proxy_url[len("socks5://") :]
  return proxy_url


def resolve_proxy_url() -> str | None:
  return (
    os.getenv("TELEGRAM_PROXY_URL", "").strip()
    or os.getenv("TELEGRAM_PROXY", "").strip()
    or None
  )


def probe_telegram_api(proxy_url: str | None = None, timeout: float = 8) -> bool:
  proxies = None
  if proxy_url:
    proxies = {"http": proxy_url, "https": proxy_url}
  try:
    response = requests.get(TELEGRAM_PROBE_URL, proxies=proxies, timeout=timeout)
    return response.status_code in (200, 302)
  except requests.RequestException:
    return False


def wait_for_proxy_ready(proxy_url: str, attempts: int = 36, delay: float = 5) -> None:
  proxy_url = normalize_proxy_url(proxy_url)
  for attempt in range(1, attempts + 1):
    if probe_telegram_api(proxy_url):
      logger.info("Tor/прокси готов")
      return
    logger.info("Ожидание Tor, попытка %s/%s", attempt, attempts)
    if attempt < attempts:
      time.sleep(delay)
  logger.warning("Tor/прокси не ответил за отведённое время")


def configure_telegram_proxy() -> str | None:
  """
  Определяет рабочий прокси для Telegram API.

  TELEGRAM_AUTO_TOR — попробовать локальный Tor, если прямой доступ недоступен.
  TELEGRAM_AUTO_START_TOR — запуск Tor (в tor_launcher, до вызова этой функции).
  """
  proxy_url = resolve_proxy_url()

  if proxy_url:
    normalized = normalize_proxy_url(proxy_url)
    if probe_telegram_api(normalized):
      logger.info("Telegram API через прокси: %s", normalized)
      return normalized

    logger.warning("Прокси %s задан, но пока недоступен — ожидание Tor...", normalized)
    wait_for_proxy_ready(normalized)
    if probe_telegram_api(normalized):
      logger.info("Telegram API через прокси: %s", normalized)
      return normalized

    raise RuntimeError(
      f"TELEGRAM_PROXY_URL={proxy_url!r} задан, но Telegram API через прокси недоступен.\n"
      "1) Запустите Tor: D:\\Tor\\start-tor.ps1\n"
      "   или: .\\scripts\\start-tor.ps1\n"
      "2) Либо включите TELEGRAM_AUTO_START_TOR=true и перезапустите: python main.py\n"
      "3) Дождитесь в логе: Bootstrapped 100%\n"
      "Альтернатива: Tor Browser → TELEGRAM_PROXY_URL=socks5h://127.0.0.1:9150"
    )

  if probe_telegram_api():
    logger.info("Прямой доступ к Telegram API доступен")
    return None

  logger.warning("api.telegram.org недоступен напрямую (типично для РФ)")

  if _env_truthy("TELEGRAM_AUTO_TOR", default=True):
    local_proxy = normalize_proxy_url(LOCAL_TOR_PROXY)
    if probe_telegram_api(local_proxy):
      logger.info("Авто-fallback: используем локальный Tor %s", local_proxy)
      return local_proxy

  raise RuntimeError(
    "Telegram API недоступен. Добавьте в .env:\n"
    "  TELEGRAM_PROXY_URL=socks5h://127.0.0.1:9050\n"
    "  TELEGRAM_AUTO_START_TOR=true\n"
    "и запустите бота: python main.py\n"
    "Или вручную: D:\\Tor\\start-tor.ps1"
  )
