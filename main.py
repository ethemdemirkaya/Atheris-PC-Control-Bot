"""Atheris PC Control Bot — giris noktasi."""
from __future__ import annotations

import asyncio
import logging
import sys
import traceback

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import CONFIG
from utils.logger import setup_logging


def _build_app() -> Application:
    from handlers import start as h_start
    from handlers import screen as h_screen
    from handlers import system as h_system
    from handlers import apps as h_apps
    from handlers import media as h_media
    from handlers import files as h_files
    from handlers import interactive as h_inter

    app = Application.builder().token(CONFIG.bot_token).build()

    # --- Genel ---
    app.add_handler(CommandHandler("start", h_start.cmd_start))
    app.add_handler(CommandHandler("help", h_start.cmd_help))
    app.add_handler(CommandHandler("menu", h_inter.cmd_menu))

    # --- Ekran ---
    app.add_handler(CommandHandler("screenshot", h_screen.cmd_screenshot))
    app.add_handler(CommandHandler("click", h_screen.cmd_click))
    app.add_handler(CommandHandler("rclick", h_screen.cmd_rclick))
    app.add_handler(CommandHandler("dclick", h_screen.cmd_dclick))
    app.add_handler(CommandHandler("type", h_screen.cmd_type))
    app.add_handler(CommandHandler("key", h_screen.cmd_key))
    app.add_handler(CommandHandler("scroll", h_screen.cmd_scroll))
    app.add_handler(CommandHandler("mouse_pos", h_screen.cmd_mouse_pos))

    # --- Sistem ---
    app.add_handler(CommandHandler("sysinfo", h_system.cmd_sysinfo))
    app.add_handler(CommandHandler("uptime", h_system.cmd_uptime))
    app.add_handler(CommandHandler("battery", h_system.cmd_battery))
    app.add_handler(CommandHandler("lock", h_system.cmd_lock))
    app.add_handler(CommandHandler("sleep", h_system.cmd_sleep))
    app.add_handler(CommandHandler("logoff", h_system.cmd_logoff))
    app.add_handler(CommandHandler("shutdown", h_system.cmd_shutdown))
    app.add_handler(CommandHandler("restart", h_system.cmd_restart))
    app.add_handler(CommandHandler("cancel_shutdown", h_system.cmd_cancel_shutdown))
    app.add_handler(h_system.callback_handler())

    # --- Uygulamalar ---
    app.add_handler(CommandHandler("run", h_apps.cmd_run))
    app.add_handler(CommandHandler("processes", h_apps.cmd_processes))
    app.add_handler(CommandHandler("kill", h_apps.cmd_kill))
    app.add_handler(CommandHandler("find", h_apps.cmd_find))

    # --- Medya ---
    app.add_handler(CommandHandler("volume", h_media.cmd_volume))
    app.add_handler(CommandHandler("mute", h_media.cmd_mute))
    app.add_handler(CommandHandler("unmute", h_media.cmd_unmute))
    app.add_handler(CommandHandler("playpause", h_media.cmd_playpause))
    app.add_handler(CommandHandler("next_track", h_media.cmd_next))
    app.add_handler(CommandHandler("prev_track", h_media.cmd_prev))
    app.add_handler(CommandHandler("webcam", h_media.cmd_webcam))

    # --- Dosya ---
    app.add_handler(CommandHandler("files", h_files.cmd_files))
    app.add_handler(CommandHandler("download", h_files.cmd_download))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, h_files.on_incoming_file))

    # --- Interaktif ---
    app.add_handler(h_inter.callback_handler())

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
