"""Sistem komutlari: shutdown, restart, lock, sleep, sysinfo, uptime, battery.

Tehlikeli komutlar (shutdown/restart/logoff) inline button ile onay alir.
"""
from __future__ import annotations

import ctypes
import logging
import os
import shlex
import subprocess
import sys
import time

import psutil
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from auth import authorized
from config import CONFIG
from utils.helpers import fmt_bytes, fmt_duration, parse_int, reply


logger = logging.getLogger(__name__)


# --------- Bilgi komutlari ---------

@authorized
async def cmd_sysinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append(
                f"  {part.device} {fmt_bytes(usage.used)}/{fmt_bytes(usage.total)} ({usage.percent}%)"
            )
        except (PermissionError, OSError):
            continue
    text = (
        f"💻 *Sistem Bilgisi*\n"
        f"CPU: {cpu}%\n"
        f"RAM: {fmt_bytes(mem.used)}/{fmt_bytes(mem.total)} ({mem.percent}%)\n"
        f"Disk:\n" + ("\n".join(disks) if disks else "  -")
    )
    await reply(update, text, parse_mode="Markdown")


@authorized
async def cmd_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    boot = psutil.boot_time()
    seconds = time.time() - boot
    await reply(update, f"⏱️ Uptime: {fmt_duration(seconds)}")


@authorized
async def cmd_battery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bat = psutil.sensors_battery()
    if bat is None:
        await reply(update, "🔌 Pil bilgisi yok (masaustu olabilir).")
        return
    plug = "şarjda" if bat.power_plugged else "pilde"
    if bat.secsleft in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN):
        rest = ""
    else:
        rest = f" — kalan ~{fmt_duration(bat.secsleft)}"
    await reply(update, f"🔋 %{bat.percent:.0f} — {plug}{rest}")


# --------- Anlik islemler ---------

def _try_unlock_service(password: str) -> tuple[bool, str]:
    """LocalSystem unlock servisine named pipe ile sifre gonder.

    Returns (ok, message). Servis yoksa veya yanit vermezse ok=False ve
    sebep mesaj olarak doner.
    """
    if sys.platform != "win32":
        return False, "Sadece Windows."
    secret = os.getenv("UNLOCK_SERVICE_SECRET", "").strip()
    if not secret:
        return False, "UNLOCK_SERVICE_SECRET tanimsiz."

    pipe_name = r"\\.\pipe\AtherisUnlock"
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE = -1
    ERROR_PIPE_BUSY = 231

    k32 = ctypes.windll.kernel32

    handle = k32.CreateFileW(
        pipe_name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None
    )
    if handle == INVALID_HANDLE or handle == 0:
        err = k32.GetLastError()
        if err == 2:  # ERROR_FILE_NOT_FOUND
            return False, "unlock servisi calismiyor (NSSM ile kur — bkz. SETUP_UNLOCK_SERVICE.md)"
        if err == ERROR_PIPE_BUSY:
            return False, "unlock servisi mesgul, tekrar dene."
        return False, f"pipe acilamadi (err={err})"
    try:
        # 5sn timeout
        k32.SetNamedPipeHandleState.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        msg_mode = ctypes.c_ulong(0x00000002)  # PIPE_READMODE_MESSAGE
        k32.SetNamedPipeHandleState(handle, ctypes.byref(msg_mode), None, None)

        payload = (secret + "\n" + password).encode("utf-8")
        written = ctypes.c_ulong(0)
        ok = k32.WriteFile(handle, payload, len(payload), ctypes.byref(written), None)
        if not ok:
            return False, f"pipe yazma hata (err={k32.GetLastError()})"

        buf = ctypes.create_string_buffer(1024)
        n = ctypes.c_ulong(0)
        ok = k32.ReadFile(handle, buf, 1024, ctypes.byref(n), None)
        if not ok:
            return False, f"pipe okuma hata (err={k32.GetLastError()})"
        resp = buf.raw[: n.value].decode("utf-8", errors="replace").strip()
        return resp.startswith("OK"), resp
    finally:
        try:
            k32.CloseHandle(handle)
        except Exception:
            pass


@authorized
async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lock ekranindan gercek unlock — LocalSystem servisi araciligiyla.

    Servis kurulmussa Winlogon desktop'a SetThreadDesktop yapip sifreyi
    gercekten yazar. Kurulu degilse fallback olarak wake-jiggle + Space
    gonderir (sadece monitoru uyandirir).
    """
    if sys.platform != "win32":
        await reply(update, "Sadece Windows'ta destekleniyor.")
        return

    password = os.getenv("UNLOCK_PASSWORD", "").strip()

    if password and os.getenv("UNLOCK_SERVICE_SECRET", "").strip():
        ok, msg = _try_unlock_service(password)
        if ok:
            await reply(update, "🔓 Servis ile unlock gonderildi (Winlogon desktop).")
            return
        # Servis yoksa / hata varsa fallback'a dus, kullaniciya nedeni bildir
        logger.info("Unlock servisi reddetti: %s — fallback'a dusuluyor", msg)
        fallback_note = f"\nServis cevabi: {msg}"
    else:
        fallback_note = (
            "\nGercek unlock icin SETUP_UNLOCK_SERVICE.md'ye bak — LocalSystem servisi + UNLOCK_SERVICE_SECRET gerekli."
        )

    # --- Fallback: wake jiggle + Space (sadece uyandirma) ---
    try:
        u32 = ctypes.windll.user32

        class _POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = _POINT()
        u32.GetCursorPos(ctypes.byref(pt))
        x0, y0 = pt.x, pt.y
        u32.SetCursorPos(x0 + 5, y0 + 5)
        time.sleep(0.05)
        u32.SetCursorPos(x0, y0)

        VK_SPACE = 0x20
        KEYEVENTF_KEYUP = 0x0002
        u32.keybd_event(VK_SPACE, 0, 0, 0)
        u32.keybd_event(VK_SPACE, 0, KEYEVENTF_KEYUP, 0)

        await reply(
            update,
            "🔓 Wake + Space gonderildi (servis yok, sadece uyandirma)." + fallback_note,
        )
    except Exception as e:
        logger.exception("unlock fallback hatasi")
        await reply(update, f"Unlock hatasi: {e}")


@authorized
async def cmd_uyari(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tam ekran modern uyari overlay'i. Subprocess ile ayri tkinter penceresi."""
    import tempfile
    from pathlib import Path

    from config import CONFIG

    text = (
        " ".join(context.args).strip()
        if context.args
        else "DIKKAT! Bu PC sahibi tarafindan kontrol ediliyor."
    )

    script = CONFIG.project_root / "utils" / "show_uyari.py"
    if not script.exists():
        await reply(update, f"show_uyari.py bulunamadi: {script}")
        return

    # Console flash olmasin diye pythonw.exe varsa onu kullan
    exe = sys.executable
    if sys.platform == "win32" and exe.lower().endswith("python.exe"):
        candidate = Path(exe).with_name("pythonw.exe")
        if candidate.exists():
            exe = str(candidate)

    creationflags = 0
    if sys.platform == "win32":
        # CREATE_NEW_PROCESS_GROUP=0x200, CREATE_NO_WINDOW=0x08000000, DETACHED_PROCESS=0x08
        creationflags = 0x00000200 | 0x08000000

    tmp_path: Path | None = None
    try:
        tf = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            suffix=".txt",
            prefix="atheris_uyari_",
        )
        tf.write(text)
        tf.close()
        tmp_path = Path(tf.name)

        subprocess.Popen(
            [exe, str(script), str(tmp_path)],
            shell=False,
            close_fds=True,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # tmp_path subprocess tarafindan okunduktan sonra silinir
        preview = text if len(text) <= 100 else text[:97] + "..."
        await reply(update, f"📢 Tam ekran uyari gosterildi: {preview}")
    except Exception as e:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass
        logger.exception("uyari hatasi")
        await reply(update, f"Hata: {e}")


@authorized
async def cmd_screen_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sadece monitoru kapatir — PC kilitli degil, bot tam kontrole sahip.

    /lock'in aksine secure desktop'a gecmez, bu yuzden /screen_on ile geri
    acilabilir ve aradan klavye/mouse komutlari calisir.
    """
    if sys.platform != "win32":
        await reply(update, "Sadece Windows'ta destekleniyor.")
        return
    try:
        HWND_BROADCAST = 0xFFFF
        WM_SYSCOMMAND = 0x0112
        SC_MONITORPOWER = 0xF170
        # 2 = off, 1 = low power, -1 = on
        ctypes.windll.user32.SendMessageW(
            HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2
        )
        await reply(
            update,
            "💤 Monitor kapatildi.\n"
            "_Not: PC kilitli degil — bot full erisime sahip. /screen\\_on ile uyandir._",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception("screen_off hatasi")
        await reply(update, f"Hata: {e}")


@authorized
async def cmd_screen_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Monitoru uyandir (mouse jiggle + SendMessage -1)."""
    if sys.platform != "win32":
        await reply(update, "Sadece Windows'ta destekleniyor.")
        return
    try:
        u32 = ctypes.windll.user32

        class _POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = _POINT()
        u32.GetCursorPos(ctypes.byref(pt))
        u32.SetCursorPos(pt.x + 3, pt.y + 3)
        time.sleep(0.05)
        u32.SetCursorPos(pt.x, pt.y)
        # SC_MONITORPOWER -1 (uint olarak 0xFFFFFFFF) bazi surumlerde lazim
        try:
            u32.SendMessageW(0xFFFF, 0x0112, 0xF170, -1)
        except Exception:
            pass
        await reply(update, "🌞 Monitor uyandirildi.")
    except Exception as e:
        logger.exception("screen_on hatasi")
        await reply(update, f"Hata: {e}")


@authorized
async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if sys.platform != "win32":
        await reply(update, "Sadece Windows'ta destekleniyor.")
        return
    try:
        ctypes.windll.user32.LockWorkStation()
        await reply(update, "🔒 Ekran kilitlendi.")
    except Exception as e:
        await reply(update, f"Kilitleme hatasi: {e}")


@authorized
async def cmd_sleep(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if sys.platform != "win32":
        await reply(update, "Sadece Windows'ta destekleniyor.")
        return
    try:
        # SetSuspendState(Hibernate=False, ForceCritical=True, DisableWakeEvent=False)
        ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
        await reply(update, "😴 Uyku modu komutu gonderildi.")
    except Exception as e:
        await reply(update, f"Uyku hatasi: {e}")


@authorized
async def cmd_cancel_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        subprocess.run(["shutdown", "/a"], check=False, shell=False)
        await reply(update, "✅ Bekleyen kapatma iptal edildi.")
    except Exception as e:
        await reply(update, f"Iptal hatasi: {e}")


# --------- Onayli tehlikeli komutlar ---------

# callback_data formati: "sys:<action>:<userid>:<delay>"
# action: shutdown | restart | logoff
# Yetkisiz cevap da geldiginde reddedilir.

def _confirm_kb(action: str, user_id: int, delay: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Onayla", callback_data=f"sys:{action}:{user_id}:{delay}"
                ),
                InlineKeyboardButton("❌ Iptal", callback_data=f"sys:cancel:{user_id}:0"),
            ]
        ]
    )


def _ask_confirm(action: str, action_label: str):
    @authorized
    async def _impl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        delay = parse_int(context.args[0] if context.args else None, 10)
        delay = max(0, min(delay, 3600))
        user_id = update.effective_user.id if update.effective_user else 0
        await reply(
            update,
            f"⚠️ {action_label} onayi — {delay} saniye sonra calisir.",
            reply_markup=_confirm_kb(action, user_id, delay),
        )

    return _impl


cmd_shutdown = _ask_confirm("shutdown", "Bilgisayari kapat")
cmd_restart = _ask_confirm("restart", "Yeniden baslat")
cmd_logoff = _ask_confirm("logoff", "Oturumu kapat")


def _exec_action(action: str, delay: int) -> None:
    """Sistem komutunu calistir. shell=False, sabit argumanlar."""
    if action == "shutdown":
        subprocess.run(["shutdown", "/s", "/t", str(delay)], check=False, shell=False)
    elif action == "restart":
        subprocess.run(["shutdown", "/r", "/t", str(delay)], check=False, shell=False)
    elif action == "logoff":
        subprocess.run(["shutdown", "/l"], check=False, shell=False)
    else:
        raise ValueError(f"Bilinmeyen aksiyon: {action}")


async def on_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    parts = query.data.split(":")
    if len(parts) != 4 or parts[0] != "sys":
        return
    _, action, owner_id_s, delay_s = parts
    user = update.effective_user
    if user is None or user.id not in CONFIG.allowed_user_ids:
        await query.answer("Yetkisiz.", show_alert=True)
        return
    try:
        owner_id = int(owner_id_s)
    except ValueError:
        await query.answer("Bozuk istek.")
        return
    if user.id != owner_id:
        await query.answer("Bu butona sadece komutu baslatan basabilir.", show_alert=True)
        return

    if action == "cancel":
        await query.answer("Iptal edildi.")
        try:
            await query.edit_message_text("❌ Iptal edildi.")
        except Exception:
            pass
        return

    delay = parse_int(delay_s, 10)
    try:
        _exec_action(action, delay)
        await query.answer("Calistirildi.")
        label = {"shutdown": "Kapatma", "restart": "Yeniden baslatma", "logoff": "Oturum kapatma"}.get(
            action, action
        )
        try:
            await query.edit_message_text(f"✅ {label} {delay}sn sonra.")
        except Exception:
            pass
    except Exception as e:
        logger.exception("sistem komutu hatasi")
        await query.answer("Hata.", show_alert=True)
        try:
            await query.edit_message_text(f"⚠️ Hata: {e}")
        except Exception:
            pass


def callback_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(on_confirm_callback, pattern=r"^sys:")
