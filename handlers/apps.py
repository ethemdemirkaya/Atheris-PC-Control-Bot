"""Uygulama / process yonetimi: /run, /processes, /kill, /find."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys

import psutil
from telegram import Update
from telegram.ext import ContextTypes

from auth import authorized
from utils.helpers import fmt_bytes, parse_int, reply


logger = logging.getLogger(__name__)


# Yaygin uygulamalar icin kisa ad eslemesi (start menuden de bulunur ama hizli yol)
_SHORTCUTS: dict[str, list[str]] = {
    "notepad": ["notepad.exe"],
    "calc": ["calc.exe"],
    "calculator": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "task": ["taskmgr.exe"],
    "taskmgr": ["taskmgr.exe"],
    "paint": ["mspaint.exe"],
    "snipping": ["snippingtool.exe"],
    "settings": ["cmd.exe", "/c", "start", "ms-settings:"],
}


@authorized
async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await reply(update, "Kullanim: /run UYGULAMA  (ornek: /run notepad)")
        return
    name = context.args[0].lower().strip()
    extra = context.args[1:]

    if name in _SHORTCUTS:
        cmd = _SHORTCUTS[name] + list(extra)
    else:
        # PATH'te exe'yi ara, yoksa direkt isimle dene
        exe = shutil.which(name) or shutil.which(f"{name}.exe")
        if exe:
            cmd = [exe, *extra]
        else:
            # Windows "start" ile baslat (URL/handler protokolleri icin)
            if sys.platform == "win32":
                cmd = ["cmd.exe", "/c", "start", "", name, *extra]
            else:
                await reply(update, f"'{name}' bulunamadi.")
                return

    try:
        # shell=False — argumanlari sistem dogrudan calistirir, injection yok
        subprocess.Popen(cmd, shell=False)
        await reply(update, f"🚀 Baslatildi: {' '.join(cmd[:3])}{' …' if len(cmd) > 3 else ''}")
    except FileNotFoundError:
        await reply(update, f"'{name}' icin executable bulunamadi.")
    except Exception as e:
        logger.exception("run hatasi")
        await reply(update, f"Calistirma hatasi: {e}")


@authorized
async def cmd_processes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    procs = []
    # Iki tur: cpu_percent ilk cagrida 0 doner — kisaca samplele
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(None)
            procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 0.3sn bekle ve tekrar oku
    import time

    time.sleep(0.3)

    rows = []
    for p in procs:
        try:
            cpu = p.cpu_percent(None)
            mem = p.memory_info().rss
            rows.append((p.info["name"] or "?", p.info["pid"], cpu, mem))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    rows.sort(key=lambda r: (r[2], r[3]), reverse=True)
    top = rows[:10]
    if not top:
        await reply(update, "Process bilgisi alinamadi.")
        return
    lines = ["⚙️ *Top 10 Process*", "`PID    CPU%   RAM     Ad`"]
    for name, pid, cpu, mem in top:
        lines.append(f"`{pid:<6} {cpu:>5.1f}  {fmt_bytes(mem):>7} {name[:30]}`")
    await reply(update, "\n".join(lines), parse_mode="Markdown")


@authorized
async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await reply(update, "Kullanim: /kill PROCESS_ADI  veya  /kill PID")
        return
    target = context.args[0].strip()

    pid = parse_int(target, 0)
    if pid > 0:
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
            await reply(update, f"💀 Sonlandirildi: {name} (PID {pid})")
            return
        except psutil.NoSuchProcess:
            await reply(update, f"PID {pid} bulunamadi.")
            return
        except psutil.AccessDenied:
            await reply(update, f"PID {pid}: erisim engellendi (admin gerekebilir).")
            return

    # Isimle: case-insensitive eslesme
    target_lower = target.lower()
    if not target_lower.endswith(".exe") and sys.platform == "win32":
        target_lower = target_lower + ".exe"
    killed = 0
    failed = 0
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if (p.info["name"] or "").lower() == target_lower:
                p.terminate()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            failed += 1
    msg = f"💀 {killed} process sonlandirildi."
    if failed:
        msg += f" ({failed} erisim engellendi)"
    if killed == 0 and failed == 0:
        msg = f"'{target}' isimli aktif process yok."
    await reply(update, msg)


@authorized
async def cmd_find(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await reply(update, "Kullanim: /find ARAMA")
        return
    q = " ".join(context.args).lower()
    matches = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = (p.info["name"] or "").lower()
            if q in name:
                matches.append((p.info["pid"], p.info["name"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not matches:
        await reply(update, f"'{q}' icin eslesme yok.")
        return
    matches.sort(key=lambda r: r[1].lower())
    lines = [f"🔎 *{len(matches)} eslesme*"]
    for pid, name in matches[:30]:
        lines.append(f"`{pid:<6} {name}`")
    if len(matches) > 30:
        lines.append(f"_+{len(matches)-30} daha_")
    await reply(update, "\n".join(lines), parse_mode="Markdown")
