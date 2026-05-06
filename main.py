"""Atheris PC Control Bot — giris noktasi."""
from __future__ import annotations

import asyncio
import logging
import sys
import traceback

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import CONFIG
from utils.logger import setup_logging


def _build_app() -> Application:
    from handlers import start as h_start
    from handlers import screen as h_screen

    app = Application.builder().token(CONFIG.bot_token).build()

    # --- Genel ---
    app.add_handler(CommandHandler("start", h_start.cmd_start))
    app.add_handler(CommandHandler("help", h_start.cmd_help))

    # --- Ekran ---
    app.add_handler(CommandHandler("screenshot", h_screen.cmd_screenshot))
    app.add_handler(CommandHandler("click", h_screen.cmd_click))
    app.add_handler(CommandHandler("rclick", h_screen.cmd_rclick))
    app.add_handler(CommandHandler("dclick", h_screen.cmd_dclick))
    app.add_handler(CommandHandler("type", h_screen.cmd_type))
    app.add_handler(CommandHandler("key", h_screen.cmd_key))
    app.add_handler(CommandHandler("scroll", h_screen.cmd_scroll))
    app.add_handler(CommandHandler("mouse_pos", h_screen.cmd_mouse_pos))

    # --- Hata yakalama ---
    app.add_error_handler(_on_error)

    return app


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log = logging.getLogger("error")
    err = context.error
    log.error("Handler hata: %s", err, exc_info=err)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(f"⚠️ Hata: {type(err).__name__}: {err}")
        except Exception:
            pass


def main() -> int:
    log = setup_logging()
    if not CONFIG.is_valid:
        log.error(
            "Konfigurasyon eksik. .env dosyasinda BOT_TOKEN ve ALLOWED_USER_IDS dolu olmali."
        )
        return 2
    log.info(
        "Bot baslatiliyor — yetkili kullanici sayisi=%d, log=%s",
        len(CONFIG.allowed_user_ids),
        CONFIG.log_level,
    )
    try:
        app = _build_app()
    except Exception:
        log.error("Bot kurulumu basarisiz:\n%s", traceback.format_exc())
        return 3

    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except (KeyboardInterrupt, SystemExit):
        log.info("Kullanici tarafindan durduruldu.")
    except Exception:
        log.error("Polling hatasi:\n%s", traceback.format_exc())
        return 4
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    raise SystemExit(main())
