"""Автозапуск Tor Expert Bundle перед стартом Telegram-бота (Windows, без Docker)."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

DEFAULT_TOR_EXE = r"D:\Tor\tor\tor.exe"
DEFAULT_TOR_CONFIG = r"D:\Tor\data\torrc"
DEFAULT_TOR_LOG = r"D:\Tor\data\tor-notices.log"
TELEGRAM_PROBE_URL = "https://api.telegram.org/"


def _env_truthy(name: str, default: bool = False) -> bool:
  raw = os.getenv(name)
  if raw is None:
    return default
  return raw.strip().lower() in {"1", "true", "yes", "on"}


def _proxy_host_port(proxy_url: str) -> tuple[str, int]:
  parsed = urlparse(proxy_url)
  if not parsed.hostname or not parsed.port:
    raise RuntimeError(
      f"TELEGRAM_PROXY_URL должен быть в формате socks5h://127.0.0.1:9050, получено: {proxy_url!r}"
    )
  return parsed.hostname, parsed.port


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
  try:
    with socket.create_connection((host, port), timeout=timeout):
      return True
  except OSError:
    return False


def _has_bootstrap(log_path: Path) -> bool:
  if not log_path.exists():
    return False
  return "Bootstrapped 100%" in log_path.read_text(encoding="utf-8", errors="ignore")


def wait_for_tor(log_path: Path, host: str, port: int, timeout_seconds: int) -> None:
  deadline = time.monotonic() + timeout_seconds
  while time.monotonic() < deadline:
    if _has_bootstrap(log_path) and is_port_open(host, port):
      return
    time.sleep(1)

  if is_port_open(host, port):
    raise RuntimeError(
      f"Tor открыл SOCKS-порт {host}:{port}, но не дошёл до Bootstrapped 100% в {log_path}.\n"
      f"Проверьте лог и мосты в {DEFAULT_TOR_CONFIG} или запустите вручную: D:\\Tor\\start-tor.ps1"
    )

  raise RuntimeError(
    f"Tor не запустился за {timeout_seconds} с: SOCKS-порт {host}:{port} не открылся.\n"
    f"Запустите вручную: D:\\Tor\\start-tor.ps1"
  )


def wait_for_tor_circuit(proxy_url: str, timeout_seconds: int = 60) -> None:
  normalized = proxy_url
  if normalized.startswith("socks5://"):
    normalized = "socks5h://" + normalized[len("socks5://") :]

  proxies = {"http": normalized, "https": normalized}
  deadline = time.monotonic() + timeout_seconds
  while time.monotonic() < deadline:
    try:
      response = requests.get(TELEGRAM_PROBE_URL, proxies=proxies, timeout=8)
      if response.status_code in (200, 302):
        logger.info("Tor circuit готов: Telegram API доступен через %s", normalized)
        return
    except requests.RequestException:
      pass
    time.sleep(2)

  raise RuntimeError(
    f"Tor поднят, но Telegram API недоступен через {normalized} за {timeout_seconds} с.\n"
    "Проверьте мосты в D:\\Tor\\data\\torrc или подождите и перезапустите бота."
  )


def start_tor_if_needed(proxy_url: str | None) -> None:
  if not _env_truthy("TELEGRAM_AUTO_START_TOR", default=True):
    logger.info("TELEGRAM_AUTO_START_TOR выключен — пропускаю автозапуск Tor")
    return

  if not proxy_url:
    raise RuntimeError(
      "TELEGRAM_AUTO_START_TOR=true, но TELEGRAM_PROXY_URL не задан.\n"
      "Добавьте в .env: TELEGRAM_PROXY_URL=socks5h://127.0.0.1:9050"
    )

  host, port = _proxy_host_port(proxy_url)
  tor_log_path = Path(os.getenv("TOR_LOG_PATH", DEFAULT_TOR_LOG))
  timeout_seconds = int(os.getenv("TOR_STARTUP_TIMEOUT", "180"))

  if is_port_open(host, port):
    if _has_bootstrap(tor_log_path):
      logger.info("Tor уже готов: %s:%s", host, port)
      wait_for_tor_circuit(proxy_url, timeout_seconds=min(60, timeout_seconds))
      return

    logger.info("SOCKS-порт %s:%s открыт, ожидаю Bootstrapped 100%%...", host, port)
    wait_for_tor(tor_log_path, host, port, timeout_seconds)
    wait_for_tor_circuit(proxy_url, timeout_seconds=min(60, timeout_seconds))
    return

  tor_exe_path = Path(os.getenv("TOR_EXE_PATH", DEFAULT_TOR_EXE))
  tor_config_path = Path(os.getenv("TOR_CONFIG_PATH", DEFAULT_TOR_CONFIG))

  if not tor_exe_path.exists():
    raise RuntimeError(
      f"Tor не найден: {tor_exe_path}\n"
      "Установите Tor Expert Bundle в D:\\Tor или укажите TOR_EXE_PATH в .env"
    )

  if not tor_config_path.exists():
    raise RuntimeError(
      f"Tor config не найден: {tor_config_path}\n"
      "Укажите TOR_CONFIG_PATH в .env или создайте torrc в D:\\Tor\\data\\"
    )

  logger.info("Запускаю Tor перед стартом бота...")
  popen_kwargs: dict = {
    "stdout": subprocess.DEVNULL,
    "stderr": subprocess.DEVNULL,
  }
  if os.name == "nt":
    popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

  subprocess.Popen([str(tor_exe_path), "-f", str(tor_config_path)], **popen_kwargs)
  wait_for_tor(tor_log_path, host, port, timeout_seconds)
  wait_for_tor_circuit(proxy_url, timeout_seconds=min(60, timeout_seconds))
  logger.info("Tor готов: %s:%s", host, port)
