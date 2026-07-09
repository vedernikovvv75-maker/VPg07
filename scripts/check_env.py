"""Validate .env configuration without printing secret values."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.settings_validation import validate_settings
from tor_launcher import is_port_open
from telegram_proxy import normalize_proxy_url, probe_telegram_api, resolve_proxy_url


def _mask(value: str) -> str:
  if not value:
    return "(empty)"
  if len(value) <= 8:
    return "***"
  return f"{value[:4]}...{value[-4:]}"


def main() -> None:
  settings = Settings.from_env()
  errors = validate_settings(settings, for_bot=False)

  print("VPg07 environment check\n")
  print(f"  TELEGRAM_BOT_TOKEN: {_mask(settings.telegram_bot_token)}")
  print(f"  PROXYAPI_KEY:       {_mask(settings.proxyapi_key)}")
  print(f"  PINECONE_INDEX:     {settings.pinecone_index_name or settings.pinecone_host or '(empty)'}")
  print(f"  PINECONE_NAMESPACE: {settings.pinecone_namespace}")
  print(f"  LOG_LEVEL:          {settings.log_level}")
  print(f"  API_TIMEOUT:        {settings.api_timeout}s")

  proxy_url = resolve_proxy_url()
  if proxy_url:
    normalized = normalize_proxy_url(proxy_url)
    host_port = normalized.rsplit("@", 1)[-1]
    print(f"  TELEGRAM_PROXY_URL: {host_port}")
    print(f"  Tor SOCKS open:     {is_port_open('127.0.0.1', 9050)}")
    print(f"  Telegram API probe: {probe_telegram_api(normalized)}")

  if errors:
    print("\nErrors:")
    for error in errors:
      print(f"  - {error}")
    raise SystemExit(1)

  print("\nOK: required variables are set.")


if __name__ == "__main__":
  main()
