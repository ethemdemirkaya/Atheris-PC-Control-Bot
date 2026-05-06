"""Ekran goruntusu, mouse ve klavye otomasyonu."""
from __future__ import annotations

import logging
import time
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


# --- Windows SendInput Unicode typer (klavye duzeninden bagimsiz) ---
import sys

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _PUL = ctypes.POINTER(ctypes.c_ulong)

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", _PUL),
        ]

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", _PUL),
        ]

    class _HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", ctypes.c_ulong),
            ("wParamL", ctypes.c_short),
            ("wParamH", ctypes.c_ushort),
        ]

    class _INPUT_I(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("ii", _INPUT_I)]

    _INPUT_KEYBOARD = 1
    _KEYEVENTF_KEYUP = 0x0002
    _KEYEVENTF_UNICODE = 0x0004
    _VK_RETURN = 0x0D
    _VK_TAB = 0x09
    _VK_BACK = 0x08

    _user32 = ctypes.windll.user32
    _SendInput = _user32.SendInput
    _SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    _SendInput.restype = wintypes.UINT

    def _send_vk(vk: int) -> None:
        extra = ctypes.c_ulong(0)
        down = _INPUT(type=_INPUT_KEYBOARD)
        down.ii.ki = _KEYBDINPUT(vk, 0, 0, 0, ctypes.pointer(extra))
        up = _INPUT(type=_INPUT_KEYBOARD)
        up.ii.ki = _KEYBDINPUT(vk, 0, _KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
        _SendInput(1, ctypes.byref(down), ctypes.sizeof(down))
        _SendInput(1, ctypes.byref(up), ctypes.sizeof(up))

    def _send_unicode_unit(unit: int) -> None:
        """Tek bir UTF-16 code unit gonder (BMP karakteri tek seferde olur)."""
        extra = ctypes.c_ulong(0)
        down = _INPUT(type=_INPUT_KEYBOARD)
        down.ii.ki = _KEYBDINPUT(0, unit, _KEYEVENTF_UNICODE, 0, ctypes.pointer(extra))
        up = _INPUT(type=_INPUT_KEYBOARD)
        up.ii.ki = _KEYBDINPUT(
            0, unit, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP, 0, ctypes.pointer(extra)
        )
        _SendInput(1, ctypes.byref(down), ctypes.sizeof(down))
        _SendInput(1, ctypes.byref(up), ctypes.sizeof(up))

    def send_unicode_char(ch: str) -> None:
        """Tek karakter gonder. \\n → Enter, \\t → Tab. Surrogate pair'leri destekler."""
        if ch == "\n":
            _send_vk(_VK_RETURN)
            return
        if ch == "\t":
            _send_vk(_VK_TAB)
            return
        if ch == "\b":
            _send_vk(_VK_BACK)
            return
        # UTF-16 LE encode et — BMP disi karakterler (emoji vb.) icin surrogate pair olur
        encoded = ch.encode("utf-16-le")
        for i in range(0, len(encoded), 2):
            unit = encoded[i] | (encoded[i + 1] << 8)
            _send_unicode_unit(unit)

    _UNICODE_TYPE_OK = True
else:
    _UNICODE_TYPE_OK = False

    def send_unicode_char(ch: str) -> None:  # type: ignore[no-redef]
        raise RuntimeError("Sadece Windows'ta destekleniyor.")


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


def _coords_or_current(args) -> tuple[int, int, bool]:
    """Args bossa mouse'un mevcut konumunu, doluysa parse edilmis (X, Y) doner.
    Ucuncu deger: koordinat verildi mi?"""
    if args and len(args) >= 2:
        return parse_int(args[0]), parse_int(args[1]), True
    x, y = pyautogui.position()
    return x, y, False


@authorized
async def cmd_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    try:
        x, y, given = _coords_or_current(context.args)
        if given:
            pyautogui.click(x=x, y=y)
        else:
            pyautogui.click()
        suffix = "" if given else " (mevcut konum)"
        await reply(update, f"🖱️ Sol tik{suffix}: ({x}, {y})")
    except Exception as e:
        logger.exception("click hatasi")
        await reply(update, f"Tik hatasi: {e}")


@authorized
async def cmd_rclick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    try:
        x, y, given = _coords_or_current(context.args)
        if given:
            pyautogui.rightClick(x=x, y=y)
        else:
            pyautogui.rightClick()
        suffix = "" if given else " (mevcut konum)"
        await reply(update, f"🖱️ Sag tik{suffix}: ({x}, {y})")
    except Exception as e:
        await reply(update, f"Tik hatasi: {e}")


@authorized
async def cmd_dclick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    try:
        x, y, given = _coords_or_current(context.args)
        if given:
            pyautogui.doubleClick(x=x, y=y)
        else:
            pyautogui.doubleClick()
        suffix = "" if given else " (mevcut konum)"
        await reply(update, f"🖱️ Cift tik{suffix}: ({x}, {y})")
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
    """Hizli yazma — SendInput Unicode (klavye duzeninden bagimsiz)."""
    if not await _ensure_gui(update):
        return
    if not context.args:
        await reply(update, "Kullanim: /type METIN")
        return
    text = " ".join(context.args)
    try:
        if _UNICODE_TYPE_OK:
            for ch in text:
                send_unicode_char(ch)
        elif pyperclip is not None:
            # Windows disi platform fallback
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.write(text, interval=0.01)
        await reply(update, f"⌨️ Yazildi: {text[:80]}{'...' if len(text) > 80 else ''}")
    except Exception as e:
        logger.exception("type hatasi")
        await reply(update, f"Yazma hatasi: {e}")


@authorized
async def cmd_write(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Her karakteri tek tek SendInput Unicode ile gonder.

    UTF-8 / Turkce harfler dahil hicbir klavye duzeninden etkilenmez —
    Windows pencereye dogrudan WM_CHAR olarak Unicode kod noktasi iletir.
    """
    if not await _ensure_gui(update):
        return
    if not context.args:
        await reply(update, "Kullanim: /write METIN")
        return
    text = " ".join(context.args)
    interval = 0.04
    try:
        if _UNICODE_TYPE_OK:
            for ch in text:
                send_unicode_char(ch)
                time.sleep(interval)
        else:
            # Fallback (Windows disi)
            for ch in text:
                if _can_ascii(ch):
                    pyautogui.write(ch, interval=0)
                elif pyperclip is not None:
                    pyperclip.copy(ch)
                    pyautogui.hotkey("ctrl", "v")
                time.sleep(interval)
        await reply(update, f"✍️ Yazildi: {text[:80]}{'...' if len(text) > 80 else ''}")
    except Exception as e:
        logger.exception("write hatasi")
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
async def cmd_hold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Modifier(ler)i basili tutup ana tusa N kez basip birak.

    Ornek: /hold alt+tab 2  →  Alt basili, Tab x2, sonra Alt birak.
    """
    if not await _ensure_gui(update):
        return
    if not context.args:
        await reply(
            update,
            "Kullanim: /hold MOD+KEY [TEKRAR]\n"
            "Ornek: /hold alt+tab 2  ya da  /hold ctrl+shift+t 1",
        )
        return
    combo = context.args[0].lower().strip()
    count = parse_int(context.args[1] if len(context.args) >= 2 else None, 1)
    count = max(1, min(count, 50))
    if "+" not in combo:
        await reply(update, "MOD+KEY formatinda olmali. Ornek: alt+tab")
        return
    parts = [p.strip() for p in combo.split("+") if p.strip()]
    if len(parts) < 2:
        await reply(update, "En az MOD+KEY ver.")
        return
    *mods, key = parts
    try:
        for m in mods:
            pyautogui.keyDown(m)
        try:
            for _ in range(count):
                pyautogui.press(key)
                time.sleep(0.08)
        finally:
            for m in reversed(mods):
                pyautogui.keyUp(m)
        await reply(update, f"⌨️ {'+'.join(mods)} basili → {key} x{count}")
    except Exception as e:
        # Modifier yukarida birakilmis olabilir — emin olmak icin tekrar release
        for m in reversed(mods):
            try:
                pyautogui.keyUp(m)
            except Exception:
                pass
        logger.exception("hold hatasi")
        await reply(update, f"Hold hatasi: {e}")


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


async def _send_mouse_pos(update: Update, header: str = "") -> None:
    msg = update.effective_message
    if msg is None:
        return
    try:
        buf, x, y, w, h = _annotated_mouse_screenshot()
        prefix = (header + "\n") if header else ""
        await msg.reply_photo(
            photo=buf,
            caption=(
                f"{prefix}🖱️ Mouse: ({x}, {y})\n"
                f"Sanal ekran: {w}x{h}\n"
                f"Yesil crosshair (inset) = pixel-precise konum"
            ),
        )
    except Exception as e:
        logger.exception("mouse_pos hatasi")
        await reply(update, f"Hata: {e}")


@authorized
async def cmd_mouse_pos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_gui(update):
        return
    await _send_mouse_pos(update)


@authorized
async def cmd_move(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mouse'u verilen mutlak (X, Y) koordinata tasi, sonra konumu gonder."""
    if not await _ensure_gui(update):
        return
    if not context.args or len(context.args) < 2:
        await reply(update, "Kullanim: /move X Y")
        return
    x, y = parse_int(context.args[0]), parse_int(context.args[1])
    # 3. argument: hareket suresi (saniye), default 0 (anlik)
    duration = 0.0
    if len(context.args) >= 3:
        try:
            duration = max(0.0, min(5.0, float(context.args[2])))
        except ValueError:
            duration = 0.0
    try:
        pyautogui.moveTo(x, y, duration=duration)
    except Exception as e:
        logger.exception("move hatasi")
        await reply(update, f"Hareket hatasi: {e}")
        return
    await _send_mouse_pos(update, header=f"➡️ Tasindi: ({x}, {y})")


@authorized
async def cmd_move_rel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mouse'u (DX, DY) kadar oteler. Negatif degerler sol/yukari."""
    if not await _ensure_gui(update):
        return
    if not context.args or len(context.args) < 2:
        await reply(update, "Kullanim: /move_rel DX DY  (negatif: sol/yukari)")
        return
    dx, dy = parse_int(context.args[0]), parse_int(context.args[1])
    duration = 0.0
    if len(context.args) >= 3:
        try:
            duration = max(0.0, min(5.0, float(context.args[2])))
        except ValueError:
            duration = 0.0
    try:
        pyautogui.moveRel(dx, dy, duration=duration)
    except Exception as e:
        logger.exception("move_rel hatasi")
        await reply(update, f"Hareket hatasi: {e}")
        return
    await _send_mouse_pos(update, header=f"↔️ Kaydirildi: ({dx:+d}, {dy:+d})")
