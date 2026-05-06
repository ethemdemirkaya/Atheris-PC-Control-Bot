"""Dosya yonetimi: /files (listele), /download, gelen dosyalari kaydet.

Guvenlik:
- FILE_ALLOWED_ROOTS disinda hicbir okuma/yazma yapilmaz.
- Path traversal (..) Path.resolve() sonrasi root prefix kontrolu ile engellenir.
- Yazma sadece Downloads klasoruna yapilir (varsa).
- Dosya boyutu MAX_FILE_SIZE_MB ile sinirlidir.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from auth import authorized
from config import CONFIG
from utils.helpers import fmt_bytes, reply


logger = logging.getLogger(__name__)


def _is_within_roots(path: Path) -> bool:
    """Path izin verilen koklerden birinin altinda mi?"""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in CONFIG.file_allowed_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _safe_path(raw: str) -> Optional[Path]:
    """Kullanici girdisini guvenli bir Path'e cevir, yoksa None."""
    if not raw:
        return None
    try:
        candidate = Path(raw).expanduser()
    except (OSError, ValueError):
        return None
    if _is_within_roots(candidate):
        return candidate.resolve()
    return None


def _downloads_dir() -> Optional[Path]:
    home = Path.home()
    candidate = home / "Downloads"
    if candidate.exists() and _is_within_roots(candidate):
        return candidate
    # Yoksa allowed root'lardan ilki
    for root in CONFIG.file_allowed_roots:
        if root.exists():
            return root
    return None


@authorized
async def cmd_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CONFIG.file_allowed_roots:
        await reply(update, "Izin verilen klasor yok. .env'de FILE\\_ALLOWED\\_ROOTS ayarla.")
        return

    if not context.args:
        # Allowed root'lari listele
        lines = ["📁 *Izin verilen kokler*"]
        for r in CONFIG.file_allowed_roots:
            lines.append(f"`{r}`")
        lines.append("\nKullanim: `/files YOL`")
        await reply(update, "\n".join(lines), parse_mode="Markdown")
        return

    raw = " ".join(context.args)
    path = _safe_path(raw)
    if path is None:
        await reply(update, "Bu yola erisim yok veya gecersiz.")
        return
    if not path.exists():
        await reply(update, "Yol bulunamadi.")
        return
    if not path.is_dir():
        await reply(update, "Bu bir klasor degil. /download ile dosya gonder.")
        return

    try:
        entries = list(path.iterdir())
    except PermissionError:
        await reply(update, "Klasor okuma izni yok.")
        return

    entries.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
    lines = [f"📁 `{path}`"]
    for e in entries[:60]:
        try:
            if e.is_dir():
                lines.append(f"📂 {e.name}/")
            else:
                size = e.stat().st_size
                lines.append(f"📄 {e.name} — {fmt_bytes(size)}")
        except (PermissionError, OSError):
            lines.append(f"❓ {e.name}")
    if len(entries) > 60:
        lines.append(f"_+{len(entries)-60} daha_")
    await reply(update, "\n".join(lines), parse_mode="Markdown")


@authorized
async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await reply(update, "Kullanim: /download TAM_YOL")
        return
    path = _safe_path(" ".join(context.args))
    if path is None:
        await reply(update, "Bu dosyaya erisim yok.")
        return
    if not path.exists() or not path.is_file():
        await reply(update, "Dosya yok.")
        return
    size = path.stat().st_size
    limit = CONFIG.max_file_size_mb * 1024 * 1024
    if size > limit:
        await reply(update, f"Dosya cok buyuk: {fmt_bytes(size)} (limit {CONFIG.max_file_size_mb}MB)")
        return
    msg = update.effective_message
    if msg is None:
        return
    try:
        with path.open("rb") as f:
            await msg.reply_document(document=f, filename=path.name, caption=f"📤 {path.name}")
    except Exception as e:
        logger.exception("download hatasi")
        await reply(update, f"Gonderilemedi: {e}")


@authorized
async def on_incoming_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return

    dest_dir = _downloads_dir()
    if dest_dir is None:
        await reply(update, "Indirme icin izinli klasor bulunamadi.")
        return

    file = None
    suggested_name: str = ""
    if msg.document:
        if msg.document.file_size and msg.document.file_size > CONFIG.max_file_size_mb * 1024 * 1024:
            await reply(update, "Dosya cok buyuk.")
            return
        file = await msg.document.get_file()
        suggested_name = msg.document.file_name or f"document_{msg.document.file_unique_id}"
    elif msg.photo:
        ph = msg.photo[-1]
        file = await ph.get_file()
        suggested_name = f"photo_{ph.file_unique_id}.jpg"
    else:
        return

    # Dosya adi temizle (klasor ayraci yok)
    safe_name = Path(suggested_name).name
    target = dest_dir / safe_name
    # Cakisma varsa numaralandir
    counter = 1
    while target.exists():
        target = dest_dir / f"{Path(safe_name).stem}_{counter}{Path(safe_name).suffix}"
        counter += 1
    # Ek bir guvenlik: target hala root altinda olmali
    if not _is_within_roots(target):
        await reply(update, "Hedef yol izinli kokler disinda.")
        return
    try:
        await file.download_to_drive(custom_path=str(target))
        await reply(update, f"✅ Kaydedildi: `{target}`", parse_mode="Markdown")
    except Exception as e:
        logger.exception("incoming file hatasi")
        await reply(update, f"Kaydedilemedi: {e}")
