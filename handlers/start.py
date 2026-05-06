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
    "<b>📋 Komut Listesi</b>\n"
    "<i>Hizli erisim icin /menu — kategori butonlari</i>\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "<b>📌 Genel</b>\n"
    "/start — Karsilama mesaji\n"
    "/help — Bu yardim\n"
    "/menu — Interaktif inline menu\n\n"
    "<b>📸 Ekran &amp; Tikla</b>\n"
    "/screenshot [monitor] — Ekran goruntusu\n"
    "/mouse_pos — Konum + anotasyonlu screenshot\n"
    "/move X Y [sure] — Mouse'u koordinata tasi\n"
    "/move_rel DX DY [sure] — Goreceli kaydir\n"
    "/click [X Y] — Sol tik (argsiz: mevcut konum)\n"
    "/rclick [X Y] — Sag tik\n"
    "/dclick [X Y] — Cift tik\n"
    "/scroll N — Scroll (+ yukari, - asagi)\n\n"
    "<b>⌨️ Klavye</b>\n"
    "/type METIN — Hizli yaz (klavye duzeninden bagimsiz)\n"
    "/write METIN — Her harfe tek tek bas (typewriter)\n"
    "/key TUS — Tek tus veya combo (enter, ctrl+c)\n"
    "/hold MOD+KEY [N] — Modifier basili + tusa N kez\n"
    "  <i>Ornek: /hold alt+tab 2</i>\n\n"
    "<b>💻 Sistem</b>\n"
    "/sysinfo — CPU / RAM / disk\n"
    "/uptime — Acik kalma suresi\n"
    "/battery — Pil durumu\n"
    "/lock — Ekrani kilitle <i>(secure desktop — bot bypass edemez)</i>\n"
    "/unlock — Lock ekraninda sifreyi gir <i>(servis kuruluysa gercek, yoksa wake)</i>\n"
    "/screen_off — Soft-lock: sadece monitoru kapat (bot tam erisimde)\n"
    "/screen_on — Monitoru uyandir\n"
    "/uyari [METIN] — Tam ekran modern uyari overlay\n"
    "/sleep — Uyku modu\n"
    "/logoff — Oturumu kapat <i>(onayli)</i>\n"
    "/shutdown [saniye] — Kapat <i>(onayli)</i>\n"
    "/restart [saniye] — Yeniden baslat <i>(onayli)</i>\n"
    "/cancel_shutdown — Bekleyen kapanmayi iptal et\n\n"
    "<b>🚀 Uygulamalar</b>\n"
    "/run AD — Uygulama baslat (notepad, calc, chrome…)\n"
    "/processes — Top 10 (CPU + RAM)\n"
    "/kill AD|PID — Process'i sonlandir\n"
    "/find ARAMA — Process adinda ara\n\n"
    "<b>🎵 Medya</b>\n"
    "/volume [0-100] — Ses seviyesi (argsiz: oku)\n"
    "/mute · /unmute — Sessize al / Ac\n"
    "/playpause · /next_track · /prev_track\n"
    "/webcam — Webcam'den foto\n\n"
    "<b>📁 Dosya</b>\n"
    "/files [yol] — Klasor listele\n"
    "/download YOL — Dosya gonder (max 50MB)\n"
    "<i>Telegram'dan dosya gonder → Downloads'a kaydedilir</i>\n\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>🔒 Tehlikeli komutlar (shutdown, restart, logoff) inline buton ile onay ister.</i>"
)


@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)


@authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            HELP, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
