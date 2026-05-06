"""Yetkilendirme: sadece whitelist'teki kullanicilar bot ile konusabilir.

Fail-closed: ALLOWED_USER_IDS bossa kimse erisemez.
"""
from __future__ import annotations

import functools
import logging
import time
from collections import deque
from typing import Awaitable, Callable, Deque, Dict

from telegram import Update
from telegram.ext import ContextTypes

from config import CONFIG


logger = logging.getLogger(__name__)


_recent_calls: Dict[int, Deque[float]] = {}


def _rate_limited(user_id: int) -> bool:
    now = time.monotonic()
    window = CONFIG.rate_limit_window
    dq = _recent_calls.setdefault(user_id, deque())
    while dq and (now - dq[0]) > window:
        dq.popleft()
    if len(dq) >= CONFIG.rate_limit_max:
        return True
    dq.append(now)
    return False


HandlerFn = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


def authorized(func: HandlerFn) -> HandlerFn:
    """Decorator: sadece whitelist + rate limit gecen handler'i calistir."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if user is None:
            return
        if not CONFIG.allowed_user_ids:
            logger.warning("Bot ALLOWED_USER_IDS bos — fail-closed, %s reddedildi", user.id)
            return
        if user.id not in CONFIG.allowed_user_ids:
            logger.warning("Yetkisiz erisim denemesi: id=%s username=%s", user.id, user.username)
            try:
                if update.effective_message:
                    await update.effective_message.reply_text("Bu botu kullanma yetkiniz yok.")
            except Exception:
                pass
            return
        if _rate_limited(user.id):
            logger.info("Rate limit asildi: id=%s", user.id)
            try:
                if update.effective_message:
                    await update.effective_message.reply_text("Cok hizli. Birazdan tekrar dene.")
            except Exception:
                pass
            return
        # Audit log: hangi kullanici hangi komutu calistirdi
        try:
            text = (update.effective_message.text if update.effective_message else "") or ""
            logger.info(
                "AUDIT id=%s username=%s handler=%s text=%r",
                user.id,
                user.username,
                func.__name__,
                text[:200],
            )
        except Exception:
            pass
        await func(update, context)

    return wrapper
