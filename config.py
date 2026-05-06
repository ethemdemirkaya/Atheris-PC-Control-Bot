"""Konfigurasyon yukleyici. .env dosyasindan tum ayarlari okur."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def _parse_ids(raw: str) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out


def _parse_paths(raw: str) -> list[Path]:
    if not raw:
        return []
    out: list[Path] = []
    for part in raw.split(","):
        part = part.strip().strip('"').strip("'")
        if not part:
            continue
        try:
            out.append(Path(part).resolve())
        except OSError:
            continue
    return out


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_user_ids: frozenset[int]
    log_level: str
    rate_limit_window: float
    rate_limit_max: int
    file_allowed_roots: tuple[Path, ...]
    max_file_size_mb: int
    project_root: Path = field(default=PROJECT_ROOT)

    @property
    def is_valid(self) -> bool:
        return bool(self.bot_token) and bool(self.allowed_user_ids)


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    ids = frozenset(_parse_ids(os.getenv("ALLOWED_USER_IDS", "")))
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    window = float(os.getenv("RATE_LIMIT_WINDOW", "10") or "10")
    max_cmd = int(os.getenv("RATE_LIMIT_MAX", "20") or "20")
    roots = tuple(_parse_paths(os.getenv("FILE_ALLOWED_ROOTS", "")))
    if not roots:
        # Default: kullaniciya guvenli klasorler
        home = Path.home()
        roots = tuple(
            p for p in (home / "Desktop", home / "Downloads", home / "Documents", home / "Pictures")
            if p.exists()
        )
    max_size = int(os.getenv("MAX_FILE_SIZE_MB", "50") or "50")
    return Config(
        bot_token=token,
        allowed_user_ids=ids,
        log_level=level,
        rate_limit_window=window,
        rate_limit_max=max_cmd,
        file_allowed_roots=roots,
        max_file_size_mb=max_size,
    )


CONFIG = load_config()
