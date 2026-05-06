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
    "/help — Bu yardim\n"
    "/menu — Interaktif menu\n\n"
    "*📸 Ekran*\n"
    "/screenshot \\[monitor\\] — Ekran goruntusu\n"
    "/click \\[X Y\\] — Sol tik \\(argsiz mevcut konum\\)\n"
    "/rclick \\[X Y\\] — Sag tik\n"
    "/dclick \\[X Y\\] — Cift tik\n"
    "/type METIN — Klavye ile yaz \\(clipboard\\)\n"
    "/write METIN — Her harfe tek tek bas\n"
    "/key TUS — Tek tus \\(enter, esc, ctrl\\+c\\.\\.\\.\\)\n"
    "/hold MOD\\+KEY \\[N\\] — Modifier basili \\+ tus N kez\n"
    "/scroll N — Scroll \\(\\+/\\-\\)\n"
    "/mouse\\_pos — Mouse konumu \\(anotasyonlu\\)\n"
    "/move X Y \\[sure\\] — Mouse'u tasi\n"
    "/move\\_rel DX DY \\[sure\\] — Goreceli kaydir\n\n"
    "*💻 Sistem*\n"
    "/sysinfo — CPU/RAM/disk\n"
    "/uptime — Acik kalma suresi\n"
    "/battery — Pil durumu\n"
    "/lock — Ekrani kilitle\n"
    "/unlock — Best\\-effort unlock \\(ekrani uyandir\\)\n"
    "/uyari \\[METIN\\] — Ekrana topmost uyari kutusu\n"
    "/sleep — Uyku modu\n"
    "/logoff — Oturumu kapat \\(onayli\\)\n"
    "/shutdown \\[saniye\\] — Kapat \\(onayli\\)\n"
    "/restart \\[saniye\\] — Yeniden baslat \\(onayli\\)\n"
    "/cancel\\_shutdown — Bekleyen kapanmayi iptal et\n\n"
    "*🚀 Uygulamalar*\n"
    "/run AD — Uygulama baslat\n"
    "/processes — En cok kaynak kullananlar\n"
    "/kill AD\\_veya\\_PID — Process'i kapat\n"
    "/find ARAMA — Process ara\n\n"
    "*🎵 Medya*\n"
    "/volume \\[0\\-100\\] — Ses seviyesi\n"
    "/mute /unmute — Sessiz / Ac\n"
    "/playpause /next\\_track /prev\\_track\n"
    "/webcam — Webcam fotograf\n\n"
    "*📁 Dosya*\n"
    "/files \\[yol\\] — Klasor listele\n"
    "/download YOL — Dosya gonder\n"
    "_Telegram'dan dosya gonder → Downloads'a kaydedilir_"
)


@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)


@authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(HELP, parse_mode=ParseMode.MARKDOWN_V2)
