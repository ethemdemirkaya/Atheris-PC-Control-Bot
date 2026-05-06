"""Tam ekran modern uyari penceresi.

Bot tarafindan ayri subprocess olarak baslatilir. Metin tek argumanda
gecirilen temp dosyasindan okunur (argv escape / uzunluk sorunu olmasin).

Kapanma: ESC, Enter, Space veya tiklamak.
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path


def _scaled_font_size(char_count: int, screen_h: int) -> int:
    if char_count <= 20:
        return max(72, int(screen_h * 0.13))
    if char_count <= 80:
        return max(52, int(screen_h * 0.085))
    if char_count <= 250:
        return max(34, int(screen_h * 0.052))
    return max(22, int(screen_h * 0.034))


def main() -> int:
    if len(sys.argv) < 2:
        return 2
    text_path = Path(sys.argv[1])
    try:
        text = text_path.read_text(encoding="utf-8").strip() or "DIKKAT!"
    except OSError:
        return 3
    finally:
        try:
            text_path.unlink()
        except OSError:
            pass

    root = tk.Tk()
    root.title("Atheris Uyari")
    root.configure(bg="#0a0a0a")
    try:
        root.attributes("-fullscreen", True)
    except tk.TclError:
        # Fallback: maximize
        root.state("zoomed")
    root.attributes("-topmost", True)
    root.focus_force()
    root.config(cursor="arrow")

    def close(_evt=None):
        try:
            root.destroy()
        except Exception:
            pass

    for seq in ("<Escape>", "<Button-1>", "<Return>", "<space>"):
        root.bind(seq, close)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    # Pulsing renkli cerceve
    border = tk.Frame(root, bg="#ff3300", highlightthickness=0)
    border.pack(fill="both", expand=True, padx=12, pady=12)
    inner = tk.Frame(border, bg="#0a0a0a")
    inner.pack(fill="both", expand=True, padx=14, pady=14)

    # Uyari ikonu
    icon_size = max(72, int(sh * 0.13))
    icon_lbl = tk.Label(
        inner,
        text="⚠",
        fg="#ffcc00",
        bg="#0a0a0a",
        font=("Segoe UI Symbol", icon_size, "bold"),
    )
    icon_lbl.pack(pady=(int(sh * 0.05), 8))

    # Mesaj yazi boyutu — uzunluga ve ekrana gore
    fsize = _scaled_font_size(len(text), sh)
    body = tk.Label(
        inner,
        text=text,
        fg="#ffffff",
        bg="#0a0a0a",
        font=("Segoe UI", fsize, "bold"),
        wraplength=int(sw * 0.86),
        justify="center",
    )
    body.pack(expand=True, fill="both", padx=int(sw * 0.04))

    # Alt yardimci yazi
    hint = tk.Label(
        inner,
        text="ESC · Enter · Space · Tik — kapat",
        fg="#777777",
        bg="#0a0a0a",
        font=("Segoe UI", 12),
    )
    hint.pack(pady=(8, int(sh * 0.035)))

    # Pulse efekti — cerceve ve ikon rengi
    palette = ["#ff3300", "#ff7a00", "#ffcc00", "#ff7a00"]
    state = {"i": 0}

    def tick() -> None:
        state["i"] = (state["i"] + 1) % len(palette)
        try:
            c = palette[state["i"]]
            border.configure(bg=c)
            icon_lbl.configure(fg=c)
            root.after(420, tick)
        except tk.TclError:
            return

    root.after(0, tick)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
