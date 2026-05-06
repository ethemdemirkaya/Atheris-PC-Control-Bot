"""/start ve /help komutlari."""
from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from auth import authorized


WELCOME = (
    "🤖 *Atheris PC Control Bot*\n\n"
    "PC'ni Telegram uzerinden uzaktan kontrol edebilirsin.\n"
    "Komut listesi icin /help yaz."
)

HELP = (
    "*📋 Komut Listesi*\n\n"
    "*Genel*\n"
    "/start — Karsilama\n"
    "/help — Bu yardim\n\n"
    "_Diger komutlar sonraki asamalarda eklenecek._"
)


@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)


@authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(HELP, parse_mode=ParseMode.MARKDOWN_V2)
