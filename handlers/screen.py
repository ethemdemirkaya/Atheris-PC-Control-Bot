"""Ekran goruntusu, mouse ve klavye otomasyonu."""
from __future__ import annotations

import logging
from io import BytesIO

from telegram import Update
from telegram.ext import ContextTypes

from auth import authorized
from utils.helpers import parse_int, reply


logger = logging.getLogger(__name__)


# pyautogui'yi import edemezsek (X server yok / izin yok) komutlar anlamli hata donsun
try:
    import pyautogui  # type: ignore

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _PYAUTOGUI_OK = True
    _PYAUTOGUI_ERR: str | None = None
except Exception as e:  # pragma: no cover
    pyautogui = None  # type: ignore
    _PYAUTOGUI_OK = False
    _PYAUTOGUI_ERR = repr(e)

try:
    import pyperclip  # type: ignore
except Exception:  # pragma: no cover
    pyperclip = None  # type: ignore

try:
    import mss  # type: ignore
except Exception:  # pragma: no cover
    mss = None  # type: ignore


async def _ensure_gui(update: Update) -> bool:
    if not _PYAUTOGUI_OK:
        await reply(update, f"GUI otomasyonu yuklenemedi: {_PYAUTOGUI_ERR}")
        return False
    return True


def _take_screenshot(monitor: int = 0) -> BytesIO:
    """Belirli monitorden screenshot al. monitor=0 → tum ekranlar, 1+ tek monitor."""
    if mss is not None:
        with mss.mss() as sct:
            mons = sct.monitors  # [0]=tum, [1..N]=tek tek
            idx = monitor if 0 <= monitor < len(mons) else 0
            shot = sct.grab(mons[idx])
            from PIL import Image  # lazy

            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            buf = BytesIO()
            img.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            buf.name = "screen.png"
            return buf
    # Fallback
    img = pyautogui.screenshot()
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = "screen.png"
    return buf


@authorized
async def cmd_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    monitor = parse_int(context.args[0] if context.args else None, 0)
    try:
        buf = _take_screenshot(monitor)
    except Exception as e:
        logger.exception("screenshot hatasi")
        await reply(update, f"Screenshot hatasi: {e}")
        return
    msg = update.effective_message
    if msg:
        await msg.reply_photo(photo=buf, caption=f"📸 Monitor {monitor}")


@authorized
async def cmd_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    if not context.args or len(context.args) < 2:
        await reply(update, "Kullanim: /click X Y")
        return
    x, y = parse_int(context.args[0]), parse_int(context.args[1])
    try:
        pyautogui.click(x=x, y=y)
        await reply(update, f"🖱️ Sol tik: ({x}, {y})")
    except Exception as e:
        logger.exception("click hatasi")
        await reply(update, f"Tik hatasi: {e}")


@authorized
async def cmd_rclick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    if not context.args or len(context.args) < 2:
        await reply(update, "Kullanim: /rclick X Y")
        return
    x, y = parse_int(context.args[0]), parse_int(context.args[1])
    try:
        pyautogui.rightClick(x=x, y=y)
        await reply(update, f"🖱️ Sag tik: ({x}, {y})")
    except Exception as e:
        await reply(update, f"Tik hatasi: {e}")


@authorized
async def cmd_dclick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    if not context.args or len(context.args) < 2:
        await reply(update, "Kullanim: /dclick X Y")
        return
    x, y = parse_int(context.args[0]), parse_int(context.args[1])
    try:
        pyautogui.doubleClick(x=x, y=y)
        await reply(update, f"🖱️ Cift tik: ({x}, {y})")
    except Exception as e:
        await reply(update, f"Tik hatasi: {e}")


def _can_ascii(text: str) -> bool:
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


@authorized
async def cmd_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    if not context.args:
        await reply(update, "Kullanim: /type METIN")
        return
    text = " ".join(context.args)
    try:
        if _can_ascii(text) or pyperclip is None:
            pyautogui.write(text, interval=0.01)
        else:
            # Turkce/Unicode → clipboard ustunden yapistir
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        await reply(update, f"⌨️ Yazildi: {text[:80]}{'...' if len(text) > 80 else ''}")
    except Exception as e:
        logger.exception("type hatasi")
        await reply(update, f"Yazma hatasi: {e}")


_KEY_MAP = {
    "ctrl+c": ("ctrl", "c"),
    "ctrl+v": ("ctrl", "v"),
    "ctrl+x": ("ctrl", "x"),
    "ctrl+z": ("ctrl", "z"),
    "ctrl+a": ("ctrl", "a"),
    "ctrl+s": ("ctrl", "s"),
    "alt+tab": ("alt", "tab"),
    "alt+f4": ("alt", "f4"),
    "win+d": ("win", "d"),
    "win+e": ("win", "e"),
    "win+r": ("win", "r"),
}


@authorized
async def cmd_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    if not context.args:
        await reply(update, "Kullanim: /key TUS  (ornek: enter, esc, f5, ctrl+c)")
        return
    key = " ".join(context.args).lower().strip()
    try:
        if key in _KEY_MAP:
            pyautogui.hotkey(*_KEY_MAP[key])
        elif "+" in key:
            parts = [p.strip() for p in key.split("+") if p.strip()]
            pyautogui.hotkey(*parts)
        else:
            pyautogui.press(key)
        await reply(update, f"⌨️ Tus: {key}")
    except Exception as e:
        logger.exception("key hatasi")
        await reply(update, f"Tus hatasi: {e}")


@authorized
async def cmd_scroll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    if not context.args:
        await reply(update, "Kullanim: /scroll N  (+ yukari, - asagi)")
        return
    amount = parse_int(context.args[0], 0)
    try:
        # pyautogui.scroll: pozitif=yukari, negatif=asagi
        pyautogui.scroll(amount * 100)
        await reply(update, f"🖱️ Scroll: {amount}")
    except Exception as e:
        await reply(update, f"Scroll hatasi: {e}")


@authorized
async def cmd_mouse_pos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    try:
        x, y = pyautogui.position()
        w, h = pyautogui.size()
        await reply(update, f"🖱️ Mouse: ({x}, {y})\nEkran: {w}x{h}")
    except Exception as e:
        await reply(update, f"Hata: {e}")
