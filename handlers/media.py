"""Medya: ses seviyesi, mute, media keys, webcam."""
from __future__ import annotations

import logging
from io import BytesIO

from telegram import Update
from telegram.ext import ContextTypes

from auth import authorized
from utils.helpers import parse_int, reply


logger = logging.getLogger(__name__)


# --- pycaw (Windows) ile sistem ses kontrolu ---
try:
    from comtypes import CLSCTX_ALL  # type: ignore
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore

    _PYCAW_OK = True
except Exception as e:  # pragma: no cover
    _PYCAW_OK = False
    _PYCAW_ERR = repr(e)


def _get_volume_iface():
    if not _PYCAW_OK:
        raise RuntimeError(f"pycaw yuklenemedi: {_PYCAW_ERR}")
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return interface.QueryInterface(IAudioEndpointVolume)


def _get_volume_pct() -> int:
    vol = _get_volume_iface()
    # GetMasterVolumeLevelScalar 0.0..1.0 doner
    return int(round(vol.GetMasterVolumeLevelScalar() * 100))


def _set_volume_pct(pct: int) -> None:
    pct = max(0, min(100, pct))
    vol = _get_volume_iface()
    vol.SetMasterVolumeLevelScalar(pct / 100.0, None)


def _set_mute(state: bool) -> None:
    vol = _get_volume_iface()
    vol.SetMute(1 if state else 0, None)


@authorized
async def cmd_volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _PYCAW_OK:
        await reply(update, f"Ses kontrolu yuklenemedi: {_PYCAW_ERR}")
        return
    try:
        if not context.args:
            cur = _get_volume_pct()
            await reply(update, f"🔊 Ses: %{cur}")
            return
        pct = parse_int(context.args[0], -1)
        if pct < 0 or pct > 100:
            await reply(update, "0-100 arasi bir deger ver.")
            return
        _set_volume_pct(pct)
        await reply(update, f"🔊 Ses %{pct} olarak ayarlandi.")
    except Exception as e:
        logger.exception("volume hatasi")
        await reply(update, f"Hata: {e}")


@authorized
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        _set_mute(True)
        await reply(update, "🔇 Sessize alindi.")
    except Exception as e:
        await reply(update, f"Hata: {e}")


@authorized
async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        _set_mute(False)
        await reply(update, "🔊 Ses acildi.")
    except Exception as e:
        await reply(update, f"Hata: {e}")


# --- Media keys (pyautogui) ---
try:
    import pyautogui  # type: ignore

    _PG_OK = True
except Exception:  # pragma: no cover
    _PG_OK = False


async def _media_press(update: Update, key: str, label: str) -> None:
    if not _PG_OK:
        await reply(update, "pyautogui yok.")
        return
    try:
        pyautogui.press(key)
        await reply(update, f"⏯️ {label}")
    except Exception as e:
        await reply(update, f"Hata: {e}")


@authorized
async def cmd_playpause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _media_press(update, "playpause", "Play/Pause")


@authorized
async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _media_press(update, "nexttrack", "Sonraki")


@authorized
async def cmd_prev(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _media_press(update, "prevtrack", "Onceki")


# --- Webcam (opencv) ---
@authorized
async def cmd_webcam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        import cv2  # type: ignore
    except Exception as e:
        await reply(update, f"opencv yuklenemedi: {e}")
        return

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
    try:
        if not cam.isOpened():
            await reply(update, "Webcam acilamadi (baska app kullaniyor olabilir).")
            return
        # Birkac frame at — ilk kareler genelde karanlik gelir
        for _ in range(5):
            cam.read()
        ok, frame = cam.read()
        if not ok or frame is None:
            await reply(update, "Webcam'den kare alinamadi.")
            return
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            await reply(update, "JPEG encode hatasi.")
            return
        buf = BytesIO(jpg.tobytes())
        buf.name = "webcam.jpg"
        msg = update.effective_message
        if msg:
            await msg.reply_photo(photo=buf, caption="📷 Webcam")
    except Exception as e:
        logger.exception("webcam hatasi")
        await reply(update, f"Hata: {e}")
    finally:
        try:
            cam.release()
        except Exception:
            pass
