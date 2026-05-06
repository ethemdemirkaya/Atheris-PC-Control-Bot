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
advapi32 = ctypes.windll.advapi32

# Pipe / file API
GENERIC_ALL = 0x10000000
PIPE_ACCESS_DUPLEX = 0x03
PIPE_TYPE_MESSAGE = 0x04
PIPE_READMODE_MESSAGE = 0x02
PIPE_WAIT = 0x00
INVALID_HANDLE = -1
ERROR_PIPE_CONNECTED = 535


# Pipe'i interactive user'a da acan SECURITY_ATTRIBUTES uret
# SDDL: SYSTEM=Full, BuiltinAdmins=Full, Interactive Users=Read+Write
class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", ctypes.c_ulong),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", ctypes.c_int),
    ]


advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
    ctypes.c_wchar_p,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_ulong),
]
advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = ctypes.c_int


def _build_pipe_sa() -> _SECURITY_ATTRIBUTES | None:
    sddl = "D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGW;;;IU)"
    psd = ctypes.c_void_p(0)
    sz = ctypes.c_ulong(0)
    ok = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, 1, ctypes.byref(psd), ctypes.byref(sz)
    )
    if not ok:
        log.error("SDDL convert hata: %s", k32.GetLastError())
        return None
    sa = _SECURITY_ATTRIBUTES(ctypes.sizeof(_SECURITY_ATTRIBUTES), psd.value, 0)
    return sa

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


def do_unlock_inplace(password: str) -> tuple[bool, str]:
    """Bu thread'de direkt unlock yap. Sadece child process'te (user session'da
    SYSTEM token ile) calisir; servisin kendisi Session 0'da bunu basaramaz."""
    saved, desk = _switch_to_winlogon()
    if not desk:
        return False, "Winlogon desktop'a gecilemedi"
    try:
        _send_vk(VK_SPACE)
        time.sleep(0.4)
        for ch in password:
            _send_unicode_char(ch)
        time.sleep(0.15)
        _send_vk(VK_RETURN)
        return True, "OK"
    finally:
        _restore_desktop(saved, desk)


# --- Session 0 → user session token + CreateProcessAsUser ---
TOKEN_DUPLICATE = 0x0002
TOKEN_QUERY = 0x0008
TOKEN_ASSIGN_PRIMARY = 0x0001
TOKEN_ADJUST_DEFAULT = 0x0080
TOKEN_ADJUST_SESSIONID = 0x0100
SecurityIdentification = 2
TokenPrimary = 1
TokenSessionId = 12
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NO_WINDOW = 0x08000000


class _STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("lpReserved", ctypes.c_wchar_p),
        ("lpDesktop", ctypes.c_wchar_p),
        ("lpTitle", ctypes.c_wchar_p),
        ("dwX", ctypes.c_ulong),
        ("dwY", ctypes.c_ulong),
        ("dwXSize", ctypes.c_ulong),
        ("dwYSize", ctypes.c_ulong),
        ("dwXCountChars", ctypes.c_ulong),
        ("dwYCountChars", ctypes.c_ulong),
        ("dwFillAttribute", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("wShowWindow", ctypes.c_ushort),
        ("cbReserved2", ctypes.c_ushort),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", ctypes.c_void_p),
        ("hStdOutput", ctypes.c_void_p),
        ("hStdError", ctypes.c_void_p),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", ctypes.c_void_p),
        ("hThread", ctypes.c_void_p),
        ("dwProcessId", ctypes.c_ulong),
        ("dwThreadId", ctypes.c_ulong),
    ]


advapi32.OpenProcessToken.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_void_p),
]
advapi32.OpenProcessToken.restype = ctypes.c_int

advapi32.DuplicateTokenEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_void_p),
]
advapi32.DuplicateTokenEx.restype = ctypes.c_int

advapi32.SetTokenInformation.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_ulong,
]
advapi32.SetTokenInformation.restype = ctypes.c_int

advapi32.CreateProcessAsUserW.argtypes = [
    ctypes.c_void_p,
    ctypes.c_wchar_p,
    ctypes.c_wchar_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_ulong,
    ctypes.c_void_p,
    ctypes.c_wchar_p,
    ctypes.POINTER(_STARTUPINFO),
    ctypes.POINTER(_PROCESS_INFORMATION),
]
advapi32.CreateProcessAsUserW.restype = ctypes.c_int

# WTSGetActiveConsoleSessionId actually lives in kernel32.dll, not wtsapi32
k32.WTSGetActiveConsoleSessionId.restype = ctypes.c_ulong


def do_unlock_via_user_session(password: str) -> tuple[bool, str]:
    """SYSTEM token'i user session'a aktar, kendini --inject ile spawnla."""
    session_id = k32.WTSGetActiveConsoleSessionId()
    if session_id == 0xFFFFFFFF:
        return False, "Aktif console session yok"
    if session_id == 0:
        return False, "Console session=0 (kullanici oturumu yok)"

    proc_token = ctypes.c_void_p()
    rights = (
        TOKEN_DUPLICATE
        | TOKEN_QUERY
        | TOKEN_ASSIGN_PRIMARY
        | TOKEN_ADJUST_DEFAULT
        | TOKEN_ADJUST_SESSIONID
    )
    if not advapi32.OpenProcessToken(k32.GetCurrentProcess(), rights, ctypes.byref(proc_token)):
        return False, f"OpenProcessToken err={k32.GetLastError()}"

    dup_token = ctypes.c_void_p()
    try:
        if not advapi32.DuplicateTokenEx(
            proc_token, 0, None, SecurityIdentification, TokenPrimary, ctypes.byref(dup_token)
        ):
            return False, f"DuplicateTokenEx err={k32.GetLastError()}"
        try:
            sid = ctypes.c_ulong(session_id)
            if not advapi32.SetTokenInformation(
                dup_token, TokenSessionId, ctypes.byref(sid), ctypes.sizeof(sid)
            ):
                return False, f"SetTokenInformation err={k32.GetLastError()}"

            # Sifreyi temp dosyada gec
            tmp = LOG_DIR / f"unlock_{int(time.time())}_{os.getpid()}.tmp"
            tmp.write_text(password, encoding="utf-8")

            si = _STARTUPINFO()
            si.cb = ctypes.sizeof(si)
            si.lpDesktop = "winsta0\\default"
            pi = _PROCESS_INFORMATION()

            cmdline = f'"{sys.executable}" "{__file__}" --inject "{tmp}"'
            cmd_buf = ctypes.create_unicode_buffer(cmdline)

            ok = advapi32.CreateProcessAsUserW(
                dup_token,
                None,
                cmd_buf,
                None,
                None,
                False,
                CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW,
                None,
                str(PROJECT_ROOT),
                ctypes.byref(si),
                ctypes.byref(pi),
            )
            if not ok:
                err = k32.GetLastError()
                try:
                    tmp.unlink()
                except OSError:
                    pass
                return False, f"CreateProcessAsUser err={err}"

            k32.WaitForSingleObject(pi.hProcess, 8000)
            exit_code = ctypes.c_ulong()
            k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code))
            k32.CloseHandle(pi.hProcess)
            k32.CloseHandle(pi.hThread)
            try:
                tmp.unlink()
            except OSError:
                pass

            if exit_code.value == 0:
                return True, "OK (child)"
            return False, f"Inject child exit={exit_code.value}"
        finally:
            k32.CloseHandle(dup_token)
    finally:
        k32.CloseHandle(proc_token)


# --- Named pipe sunucu ---
def _write(pipe, text: str) -> None:
    payload = text.encode("utf-8")
    written = ctypes.c_ulong(0)
    k32.WriteFile(pipe, payload, len(payload), ctypes.byref(written), None)


def serve() -> int:
    log.info("Servis baslatiliyor — pipe=%s, secret=%s", PIPE_NAME, "var" if SHARED_SECRET else "YOK")
    if not SHARED_SECRET:
        log.warning("UNLOCK_SERVICE_SECRET bos — istemci dogrulamasi yok!")
    sa = _build_pipe_sa()
    if sa is None:
        log.error("Pipe SECURITY_ATTRIBUTES uretilemedi — interactive kullanici pipe'a erisemeyecek!")
    while True:
        pipe = k32.CreateNamedPipeW(
            PIPE_NAME,
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
            1,
            4096,
            4096,
            0,
            ctypes.byref(sa) if sa is not None else None,
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
            ok2, msg = do_unlock_via_user_session(password)
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


def _inject_main(tmp_path: str) -> int:
    """Child process modu — user session'da SYSTEM token ile direkt inject."""
    p = Path(tmp_path)
    try:
        password = p.read_text(encoding="utf-8")
    except Exception:
        log.exception("Inject child: temp okunamadi")
        return 10
    finally:
        try:
            p.unlink()
        except OSError:
            pass
    ok, msg = do_unlock_inplace(password)
    log.info("Inject child sonuc: ok=%s msg=%s", ok, msg)
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.platform != "win32":
        log.error("Sadece Windows.")
        sys.exit(2)
    if "--inject" in sys.argv:
        idx = sys.argv.index("--inject")
        if idx + 1 < len(sys.argv):
            sys.exit(_inject_main(sys.argv[idx + 1]))
        sys.exit(99)
    try:
        sys.exit(serve())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        log.exception("serve crash")
        sys.exit(1)
