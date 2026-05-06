"""Atheris Unlock Service — LocalSystem'de calisan kucuk Windows servisi.

Lock ekranindan sifreyi gercekten girebilmek icin Winlogon desktop'a
`SetThreadDesktop` yapmak ve oradan SendInput cagirmak gerekir. Bunu
sadece SYSTEM hesabi yapabilir; bu yuzden bu script NSSM araciligi ile
LocalSystem servisi olarak kurulur.

Bot tarafi /unlock komutunda named pipe `\\\\.\\pipe\\AtherisUnlock` uzerinden
sifreyi (paylasilan secret ile imzali) gonderir; servis kabul ederse
Winlogon'a tas, sifreyi yaz, Enter, geri don.

Kurulum: bkz. SETUP_UNLOCK_SERVICE.md
"""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import time
from ctypes import wintypes
from logging.handlers import RotatingFileHandler
from pathlib import Path


# --- Konfigurasyon ---
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
PIPE_NAME = r"\\.\pipe\AtherisUnlock"


def _setup_logging() -> logging.Logger:
    log = logging.getLogger("unlock_service")
    log.setLevel(logging.INFO)
    if log.handlers:
        return log
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")
    fh = RotatingFileHandler(
        LOG_DIR / "unlock_service.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    log.addHandler(fh)
    return log


log = _setup_logging()


# --- .env yukle (servis baska working dir'den baslayabilir) ---
def _load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        log.exception(".env yuklenemedi")


_load_env()
SHARED_SECRET = os.getenv("UNLOCK_SERVICE_SECRET", "").strip()


# --- Win32 ---
k32 = ctypes.windll.kernel32
u32 = ctypes.windll.user32

# Pipe / file API
GENERIC_ALL = 0x10000000
PIPE_ACCESS_DUPLEX = 0x03
PIPE_TYPE_MESSAGE = 0x04
PIPE_READMODE_MESSAGE = 0x02
PIPE_WAIT = 0x00
INVALID_HANDLE = -1
ERROR_PIPE_CONNECTED = 535

# SendInput
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
VK_TAB = 0x09
VK_BACK = 0x08
VK_SPACE = 0x20


_PUL = ctypes.POINTER(ctypes.c_ulong)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", _PUL),
    ]


class _INPUT_I(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", _INPUT_I)]


u32.OpenDesktopW.restype = wintypes.HANDLE
u32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
u32.OpenInputDesktop.restype = wintypes.HANDLE
u32.SetThreadDesktop.restype = wintypes.BOOL
u32.CloseDesktop.restype = wintypes.BOOL


def _switch_to_winlogon():
    saved = u32.OpenInputDesktop(0, False, GENERIC_ALL)
    desk = u32.OpenDesktopW("Winlogon", 0, False, GENERIC_ALL)
    if not desk:
        log.error("OpenDesktopW(Winlogon) hata: %s", k32.GetLastError())
        return None, None
    if not u32.SetThreadDesktop(desk):
        log.error("SetThreadDesktop hata: %s", k32.GetLastError())
        u32.CloseDesktop(desk)
        return None, None
    return saved, desk


def _restore_desktop(saved, desk) -> None:
    if saved:
        try:
            u32.SetThreadDesktop(saved)
        except Exception:
            pass
    if desk:
        try:
            u32.CloseDesktop(desk)
        except Exception:
            pass


def _send_vk(vk: int) -> None:
    extra = ctypes.c_ulong(0)
    d = _INPUT(type=INPUT_KEYBOARD)
    d.ii.ki = _KEYBDINPUT(vk, 0, 0, 0, ctypes.pointer(extra))
    up = _INPUT(type=INPUT_KEYBOARD)
    up.ii.ki = _KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
    u32.SendInput(1, ctypes.byref(d), ctypes.sizeof(d))
    u32.SendInput(1, ctypes.byref(up), ctypes.sizeof(up))


def _send_unicode_char(ch: str) -> None:
    if ch == "\n":
        _send_vk(VK_RETURN)
        return
    if ch == "\t":
        _send_vk(VK_TAB)
        return
    if ch == "\b":
        _send_vk(VK_BACK)
        return
    encoded = ch.encode("utf-16-le")
    extra = ctypes.c_ulong(0)
    for i in range(0, len(encoded), 2):
        unit = encoded[i] | (encoded[i + 1] << 8)
        d = _INPUT(type=INPUT_KEYBOARD)
        d.ii.ki = _KEYBDINPUT(0, unit, KEYEVENTF_UNICODE, 0, ctypes.pointer(extra))
        up = _INPUT(type=INPUT_KEYBOARD)
        up.ii.ki = _KEYBDINPUT(
            0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, ctypes.pointer(extra)
        )
        u32.SendInput(1, ctypes.byref(d), ctypes.sizeof(d))
        u32.SendInput(1, ctypes.byref(up), ctypes.sizeof(up))


def do_unlock(password: str) -> tuple[bool, str]:
    """Winlogon desktop'a tas, swipe gec, sifreyi yaz, Enter."""
    saved, desk = _switch_to_winlogon()
    if not desk:
        return False, "Winlogon desktop'a gecilemedi (servis LocalSystem mi?)"
    try:
        _send_vk(VK_SPACE)  # Lock screen swipe gec
        time.sleep(0.4)
        for ch in password:
            _send_unicode_char(ch)
        time.sleep(0.15)
        _send_vk(VK_RETURN)
        return True, "OK"
    finally:
        _restore_desktop(saved, desk)


# --- Named pipe sunucu ---
def _write(pipe, text: str) -> None:
    payload = text.encode("utf-8")
    written = ctypes.c_ulong(0)
    k32.WriteFile(pipe, payload, len(payload), ctypes.byref(written), None)


def serve() -> int:
    log.info("Servis baslatiliyor — pipe=%s, secret=%s", PIPE_NAME, "var" if SHARED_SECRET else "YOK")
    if not SHARED_SECRET:
        log.warning("UNLOCK_SERVICE_SECRET bos — istemci dogrulamasi yok!")
    while True:
        pipe = k32.CreateNamedPipeW(
            PIPE_NAME,
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
            1,
            4096,
            4096,
            0,
            None,
        )
        if pipe == INVALID_HANDLE or pipe == 0:
            log.error("CreateNamedPipeW hata: %s", k32.GetLastError())
            time.sleep(2)
            continue
        connected = bool(k32.ConnectNamedPipe(pipe, None))
        if not connected:
            err = k32.GetLastError()
            if err != ERROR_PIPE_CONNECTED:
                log.error("ConnectNamedPipe hata: %s", err)
                k32.CloseHandle(pipe)
                continue
        try:
            buf = ctypes.create_string_buffer(8192)
            n = ctypes.c_ulong(0)
            ok = k32.ReadFile(pipe, buf, 8192, ctypes.byref(n), None)
            if not ok or n.value == 0:
                continue
            data = buf.raw[: n.value].decode("utf-8", errors="replace")
            parts = data.split("\n", 1)
            if len(parts) != 2:
                _write(pipe, "ERR bad payload")
                continue
            client_secret, password = parts
            if SHARED_SECRET and client_secret != SHARED_SECRET:
                _write(pipe, "ERR auth")
                log.warning("Auth fail")
                continue
            ok2, msg = do_unlock(password)
            _write(pipe, ("OK " + msg) if ok2 else ("ERR " + msg))
            log.info("Unlock denemesi: ok=%s msg=%s", ok2, msg)
        except Exception:
            log.exception("Pipe handler crash")
        finally:
            try:
                k32.DisconnectNamedPipe(pipe)
            except Exception:
                pass
            k32.CloseHandle(pipe)


if __name__ == "__main__":
    if sys.platform != "win32":
        log.error("Sadece Windows.")
        sys.exit(2)
    try:
        sys.exit(serve())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        log.exception("serve crash")
        sys.exit(1)
