"""Interaktif menu: inline keyboard ile hizli komutlar.

callback_data prefix: 'menu:' — sistem onaylari ile (sys:) catismaz.
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from auth import authorized
from config import CONFIG
from utils.helpers import reply


logger = logging.getLogger(__name__)


def _root_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📸 Ekran", callback_data="menu:cat:screen"),
                InlineKeyboardButton("💻 Sistem", callback_data="menu:cat:system"),
            ],
            [
                InlineKeyboardButton("🚀 Apps", callback_data="menu:cat:apps"),
                InlineKeyboardButton("🎵 Medya", callback_data="menu:cat:media"),
            ],
        ]
    )


def _back_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton("⬅️ Geri", callback_data="menu:cat:root")]


def _kb(category: str) -> InlineKeyboardMarkup:
    if category == "screen":
        rows = [
            [InlineKeyboardButton("📸 Screenshot", callback_data="menu:do:screenshot")],
            [InlineKeyboardButton("🖱️ Mouse pos", callback_data="menu:do:mouse_pos")],
            _back_row(),
        ]
    elif category == "system":
        rows = [
            [
                InlineKeyboardButton("ℹ️ Sysinfo", callback_data="menu:do:sysinfo"),
                InlineKeyboardButton("⏱️ Uptime", callback_data="menu:do:uptime"),
            ],
            [
                InlineKeyboardButton("🔋 Battery", callback_data="menu:do:battery"),
                InlineKeyboardButton("🔒 Lock", callback_data="menu:do:lock"),
            ],
            [InlineKeyboardButton("😴 Sleep", callback_data="menu:do:sleep")],
            _back_row(),
        ]
    elif category == "apps":
        rows = [
            [InlineKeyboardButton("⚙️ Top processes", callback_data="menu:do:processes")],
            _back_row(),
        ]
    elif category == "media":
        rows = [
            [
                InlineKeyboardButton("⏯️", callback_data="menu:do:playpause"),
                InlineKeyboardButton("⏭️", callback_data="menu:do:next_track"),
                InlineKeyboardButton("⏮️", callback_data="menu:do:prev_track"),
            ],
            [
                InlineKeyboardButton("🔇 Mute", callback_data="menu:do:mute"),
                InlineKeyboardButton("🔊 Unmute", callback_data="menu:do:unmute"),
            ],
            [InlineKeyboardButton("📷 Webcam", callback_data="menu:do:webcam")],
            _back_row(),
        ]
    else:
        return _root_kb()
    return InlineKeyboardMarkup(rows)


@authorized
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply(update, "🤖 Menu — bir kategori sec:", reply_markup=_root_kb())


# Komut callback'inden simulate edilen update'le tekrar handler cagiramiyoruz; en kolay yol:
# direkt ilgili handler fonksiyonunu cagirmak (CallbackContext args bos olarak).

async def on_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    user = update.effective_user
    if user is None or user.id not in CONFIG.allowed_user_ids:
        await query.answer("Yetkisiz.", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) < 3 or parts[0] != "menu":
        return
    kind, value = parts[1], parts[2]

    await query.answer()

    if kind == "cat":
        if value == "root":
            try:
                await query.edit_message_text("🤖 Menu — bir kategori sec:", reply_markup=_root_kb())
            except Exception:
                pass
            return
        title = {
            "screen": "📸 Ekran",
            "system": "💻 Sistem",
            "apps": "🚀 Apps",
            "media": "🎵 Medya",
        }.get(value, "Menu")
        try:
            await query.edit_message_text(f"{title}", reply_markup=_kb(value))
        except Exception:
            pass
        return

    if kind == "do":
        # Argument'siz handler'lari yeniden cagir. context.args yoksa varsayilanlar gecerli.
        context.args = []  # type: ignore[assignment]
        from handlers import screen as h_screen
        from handlers import system as h_system
        from handlers import apps as h_apps
        from handlers import media as h_media

        dispatch = {
            # screen
            "screenshot": h_screen.cmd_screenshot,
            "mouse_pos": h_screen.cmd_mouse_pos,
            # system
            "sysinfo": h_system.cmd_sysinfo,
            "uptime": h_system.cmd_uptime,
            "battery": h_system.cmd_battery,
            "lock": h_system.cmd_lock,
            "sleep": h_system.cmd_sleep,
            # apps
            "processes": h_apps.cmd_processes,
            # media
            "playpause": h_media.cmd_playpause,
            "next_track": h_media.cmd_next,
            "prev_track": h_media.cmd_prev,
            "mute": h_media.cmd_mute,
            "unmute": h_media.cmd_unmute,
            "webcam": h_media.cmd_webcam,
        }
        fn = dispatch.get(value)
        if fn is None:
            return
        try:
            await fn(update, context)
        except Exception:
            logger.exception("menu dispatch hatasi: %s", value)


def callback_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(on_menu_callback, pattern=r"^menu:")
