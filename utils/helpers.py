"""Ortak yardimci fonksiyonlar."""
from __future__ import annotations

import logging
from io import BytesIO
from typing import Optional

from telegram import Update


logger = logging.getLogger(__name__)


def fmt_bytes(n: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.1f} {units[i]}"


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}g")
    if hours:
        parts.append(f"{hours}sa")
    if minutes:
        parts.append(f"{minutes}dk")
    parts.append(f"{secs}sn")
    return " ".join(parts)


async def reply(update: Update, text: str, **kwargs) -> None:
    """Mesaj veya callback query'ye guvenli sekilde cevap yaz."""
    msg = update.effective_message
    if msg is None:
        return
    try:
        await msg.reply_text(text, **kwargs)
    except Exception:
        logger.exception("reply_text basarisiz")


def image_to_bytesio(image, fmt: str = "PNG") -> BytesIO:
    buf = BytesIO()
    image.save(buf, format=fmt)
    buf.seek(0)
    buf.name = f"image.{fmt.lower()}"
    return buf


def parse_int(value: Optional[str], default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
