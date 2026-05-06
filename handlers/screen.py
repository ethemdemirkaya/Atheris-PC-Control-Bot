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


def _annotated_mouse_screenshot() -> tuple[BytesIO, int, int, int, int]:
    """Tum sanal masaustunu cek, cursor pozisyonunu crosshair + zoom inset ile isaretle.

    Returns: (png_buf, abs_x, abs_y, screen_w, screen_h)
    """
    from PIL import Image, ImageDraw  # lazy

    abs_x, abs_y = pyautogui.position()

    if mss is not None:
        with mss.mss() as sct:
            mon = sct.monitors[0]  # 0 = tum sanal masaustu
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            offset_x = int(mon["left"])
            offset_y = int(mon["top"])
    else:
        img = pyautogui.screenshot()
        offset_x = offset_y = 0

    cx = abs_x - offset_x
    cy = abs_y - offset_y
    cx_clamped = max(0, min(img.width - 1, cx))
    cy_clamped = max(0, min(img.height - 1, cy))

    draw = ImageDraw.Draw(img)
    # Tam ekran crosshair
    draw.line([(cx_clamped, 0), (cx_clamped, img.height)], fill=(255, 0, 0), width=1)
    draw.line([(0, cy_clamped), (img.width, cy_clamped)], fill=(255, 0, 0), width=1)
    # Cursor halkasi
    r = 24
    draw.ellipse(
        [cx_clamped - r, cy_clamped - r, cx_clamped + r, cy_clamped + r],
        outline=(255, 0, 0),
        width=3,
    )
    draw.ellipse(
        [cx_clamped - 3, cy_clamped - 3, cx_clamped + 3, cy_clamped + 3],
        fill=(255, 255, 0),
        outline=(255, 0, 0),
    )

    # Zoom inset — cursor etrafindaki 200x200 alani 400x400'e nearest scale
    zsize = 200
    zdisp = 400
    x0 = max(0, cx_clamped - zsize // 2)
    y0 = max(0, cy_clamped - zsize // 2)
    x1 = min(img.width, x0 + zsize)
    y1 = min(img.height, y0 + zsize)
    if x1 - x0 < 10 or y1 - y0 < 10:
        # Cok kucuk bir bolge — atla
        pass
    else:
        crop = img.crop((x0, y0, x1, y1)).resize((zdisp, zdisp), Image.NEAREST)
        cdraw = ImageDraw.Draw(crop)
        sx = zdisp / max(1, x1 - x0)
        sy = zdisp / max(1, y1 - y0)
        icx = int((cx_clamped - x0) * sx)
        icy = int((cy_clamped - y0) * sy)
        cdraw.line([(icx, 0), (icx, zdisp)], fill=(0, 255, 0), width=2)
        cdraw.line([(0, icy), (zdisp, icy)], fill=(0, 255, 0), width=2)
        cdraw.ellipse(
            [icx - 6, icy - 6, icx + 6, icy + 6],
            fill=(255, 255, 0),
            outline=(255, 0, 0),
            width=2,
        )
        # Sol uste yapistir + mavi cerceve
        img.paste(crop, (10, 10))
        draw.rectangle([10, 10, 10 + zdisp, 10 + zdisp], outline=(0, 0, 255), width=4)
        # Inset basligi
        draw.rectangle([10, 10, 10 + zdisp, 36], fill=(0, 0, 255))
        draw.text((18, 14), f"ZOOM x{zdisp / zsize:.0f}  ({abs_x}, {abs_y})", fill=(255, 255, 255))

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = "mouse_pos.png"
    return buf, abs_x, abs_y, img.width, img.height


@authorized
async def cmd_mouse_pos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    msg = update.effective_message
    if msg is None:
        return
    try:
        buf, x, y, w, h = _annotated_mouse_screenshot()
        await msg.reply_photo(
            photo=buf,
            caption=(
                f"🖱️ Mouse: ({x}, {y})\n"
                f"Sanal ekran: {w}x{h}\n"
                f"Yesil crosshair (inset) = pixel-precise konum"
            ),
        )
    except Exception as e:
        logger.exception("mouse_pos hatasi")
        await reply(update, f"Hata: {e}")
