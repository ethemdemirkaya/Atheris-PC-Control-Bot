"""Loglama setup'i. Hem dosyaya hem konsola yazar."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import CONFIG


_LOG_DIR = CONFIG.project_root / "logs"
_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging() -> logging.Logger:
    _LOG_DIR.mkdir(exist_ok=True)
    level = getattr(logging, CONFIG.log_level, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Idempotent: ayni handler'lari tekrar ekleme
    if any(getattr(h, "_atheris", False) for h in root.handlers):
        return root

    formatter = logging.Formatter(_FMT)

    file_handler = RotatingFileHandler(
        _LOG_DIR / "bot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler._atheris = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    stream._atheris = True  # type: ignore[attr-defined]
    root.addHandler(stream)

    # python-telegram-bot cok gurultulu — INFO uzeri biraktir
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)

    return root
