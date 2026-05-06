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
    "*📸 Ekran*\n"
    "/screenshot \\[monitor\\] — Ekran goruntusu\n"
    "/click X Y — Sol tik\n"
    "/rclick X Y — Sag tik\n"
    "/dclick X Y — Cift tik\n"
    "/type METIN — Klavye ile yaz\n"
    "/key TUS — Tek tus \\(enter, esc, f5, ctrl\\+c\\.\\.\\.\\)\n"
    "/scroll N — Scroll \\(\\+/\\-\\)\n"
    "/mouse\\_pos — Mouse konumu\n\n"
    "*💻 Sistem*\n"
    "/sysinfo — CPU/RAM/disk\n"
    "/uptime — Acik kalma suresi\n"
    "/battery — Pil durumu\n"
    "/lock — Ekrani kilitle\n"
    "/sleep — Uyku modu\n"
    "/logoff — Oturumu kapat \\(onayli\\)\n"
    "/shutdown \\[saniye\\] — Kapat \\(onayli\\)\n"
    "/restart \\[saniye\\] — Yeniden baslat \\(onayli\\)\n"
    "/cancel\\_shutdown — Bekleyen kapanmayi iptal et"
)


@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)


@authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(HELP, parse_mode=ParseMode.MARKDOWN_V2)
