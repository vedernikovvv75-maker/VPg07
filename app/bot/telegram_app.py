from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, TypeHandler, filters

from app.bot import messages
from app.bot.handlers import BotHandlers
from app.bot.telegram_files import download_telegram_document
from app.config import Settings

logger = logging.getLogger(__name__)

TELEGRAM_MAX_FILE_BYTES = 20 * 1024 * 1024
_MIME_EXTENSIONS = {
  "application/pdf": ".pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
  "application/msword": ".doc",
  "text/plain": ".txt",
}


def _env_truthy(name: str, default: bool = False) -> bool:
  raw = os.getenv(name)
  if raw is None:
    return default
  return raw.strip().lower() in {"1", "true", "yes", "on"}


def _file_timeouts() -> dict[str, int]:
  timeout = int(os.getenv("TELEGRAM_FILE_TIMEOUT", "300"))
  return {
    "read_timeout": timeout,
    "write_timeout": timeout,
    "connect_timeout": int(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "45")),
    "pool_timeout": int(os.getenv("TELEGRAM_POOL_TIMEOUT", "45")),
  }


def _safe_file_name(document_name: str | None, file_id: str, mime_type: str | None) -> str:
  raw_name = (document_name or "").strip() or f"document_{file_id}"
  name = Path(raw_name).name
  name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
  if not name:
    name = f"document_{file_id}"
  if not Path(name).suffix and mime_type:
    name += _MIME_EXTENSIONS.get(mime_type, "")
  if not Path(name).suffix:
    name += ".bin"
  return name[:180]


async def _ensure_handlers(context: ContextTypes.DEFAULT_TYPE) -> BotHandlers:
  app = context.application
  handlers = app.bot_data.get("handlers")
  if handlers is not None:
    return handlers

  lock: asyncio.Lock = app.bot_data["handlers_lock"]
  async with lock:
    handlers = app.bot_data.get("handlers")
    if handlers is not None:
      return handlers

    settings: Settings = app.bot_data["settings"]
    logger.info("Initializing RAG pipelines (first request)...")

    from main import build_app

    handlers = await asyncio.to_thread(build_app, settings)
    app.bot_data["handlers"] = handlers
    logger.info("RAG pipelines ready")
    return handlers


async def _on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  if update.message:
    await update.message.reply_text(messages.START)


async def _on_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  if update.message:
    await update.message.reply_text(messages.HELP)


async def _log_incoming_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  message = update.message
  if not message:
    return
  # Log full update for debugging document delivery issues.
  try:
    logger.info("Incoming full update: %s", update.to_dict())
  except Exception:
    logger.exception("Failed to serialize update for logging")

  parts: list[str] = []
  if message.text:
    parts.append(f"text={message.text[:60]!r}")
  if message.document:
    parts.append(
      f"document={message.document.file_name!r} "
      f"mime={message.document.mime_type!r} "
      f"size={message.document.file_size}"
    )
  if message.photo:
    parts.append("photo")

  logger.info(
    "Telegram update chat_id=%s user_id=%s [%s]",
    message.chat_id,
    update.effective_user.id if update.effective_user else None,
    ", ".join(parts) or message.content_type,
  )


async def _on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  message = update.message
  if not message or not message.document:
    return

  document = message.document
  file_name = _safe_file_name(document.file_name, document.file_id, document.mime_type)
  timeouts = _file_timeouts()
  proxy_url = context.application.bot_data.get("proxy_url")

  logger.info(
    "Document received: name=%r mime=%r size=%s file_id=%s",
    file_name,
    document.mime_type,
    document.file_size,
    document.file_id,
  )

  if document.file_size and document.file_size > TELEGRAM_MAX_FILE_BYTES:
    await message.reply_text(messages.FILE_TOO_LARGE)
    return

  await message.reply_text(messages.FILE_RECEIVED)

  try:
    await context.bot.send_chat_action(
      chat_id=message.chat_id,
      action=ChatAction.UPLOAD_DOCUMENT,
    )

    with tempfile.TemporaryDirectory(prefix="vpg07_") as tmpdir:
      file_path = Path(tmpdir) / file_name
      logger.info("Downloading Telegram file %s -> %s", document.file_id, file_path)
      size = await download_telegram_document(
        context.bot,
        document.file_id,
        file_path,
        proxy_url=proxy_url,
        timeouts=timeouts,
      )
      logger.info("Downloaded %d bytes, waiting for pipelines", size)
      await message.reply_text(messages.FILE_DOWNLOADED)

      handlers = await _ensure_handlers(context)

      await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action=ChatAction.TYPING,
      )
      user_id = str(update.effective_user.id) if update.effective_user else None
      status, summary = await handlers.on_document(
        str(file_path),
        file_name,
        user_id=user_id,
      )

  except Exception:
    logger.exception("Document handler failed for %s", file_name)
    await message.reply_text(messages.FILE_ERROR)
    return

  await message.reply_text(status)
  if summary:
    await message.reply_text(summary)


async def _on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  if update.message:
    await update.message.reply_text(messages.SEND_AS_FILE)


async def _on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  message = update.message
  if not message or not message.text:
    return

  handlers = await _ensure_handlers(context)
  user_id = str(update.effective_user.id) if update.effective_user else None
  answer = await handlers.on_message(message.text, user_id=user_id)
  await message.reply_text(answer)


async def _on_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  message = update.message
  if not message or message.document or message.photo:
    return
  await message.reply_text(messages.UNSUPPORTED_MESSAGE)


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
  logger.exception("Unhandled Telegram error: %s", context.error)
  if isinstance(update, Update) and update.effective_message:
    await update.effective_message.reply_text(messages.QUESTION_ERROR)


def build_application(
  token: str,
  settings: Settings,
  proxy_url: str | None = None,
) -> Application:
  builder = (
    Application.builder()
    .token(token)
    .concurrent_updates(True)
    .connect_timeout(int(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "45")))
    .read_timeout(int(os.getenv("TELEGRAM_READ_TIMEOUT", "120")))
    .write_timeout(int(os.getenv("TELEGRAM_WRITE_TIMEOUT", "120")))
    .pool_timeout(int(os.getenv("TELEGRAM_POOL_TIMEOUT", "45")))
    .get_updates_connect_timeout(int(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "45")))
    .get_updates_read_timeout(int(os.getenv("TELEGRAM_READ_TIMEOUT", "120")))
    .get_updates_write_timeout(int(os.getenv("TELEGRAM_WRITE_TIMEOUT", "120")))
    .get_updates_pool_timeout(int(os.getenv("TELEGRAM_POOL_TIMEOUT", "45")))
    .post_init(_post_init)
  )

  if proxy_url:
    builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)

  application = builder.build()
  application.bot_data["settings"] = settings
  application.bot_data["handlers"] = None
  application.bot_data["handlers_lock"] = asyncio.Lock()
  application.bot_data["proxy_url"] = proxy_url

  application.add_handler(TypeHandler(Update, _log_incoming_update), group=-1)
  application.add_handler(CommandHandler("start", _on_start))
  application.add_handler(CommandHandler("help", _on_help))
  application.add_handler(MessageHandler(filters.Document.ALL, _on_document))
  application.add_handler(MessageHandler(filters.PHOTO, _on_photo))
  application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_text))
  application.add_handler(MessageHandler(~filters.COMMAND, _on_unsupported))
  application.add_error_handler(_on_error)

  return application


async def _post_init(application: Application) -> None:
  drop_pending = bool(application.bot_data.get("drop_pending_updates", False))
  await application.bot.delete_webhook(drop_pending_updates=drop_pending)
  logger.info("Webhook снят, режим polling активен (drop_pending_updates=%s)", drop_pending)

  me = await application.bot.get_me()
  proxy = application.bot_data.get("proxy_url")
  logger.info("Бот запущен: @%s (polling, proxy=%s)", me.username, proxy or "direct")
  logger.info("Напишите боту /start — инструкция по отправке PDF придёт в чат.")


def run_bot(token: str, settings: Settings, proxy_url: str | None = None) -> None:
  drop_pending = _env_truthy("TELEGRAM_DROP_PENDING_UPDATES", default=False)
  application = build_application(token, settings, proxy_url=proxy_url)
  application.bot_data["drop_pending_updates"] = drop_pending
  logger.info("Telegram bot: starting polling (drop_pending_updates=%s)", drop_pending)
  application.run_polling(drop_pending_updates=drop_pending)
