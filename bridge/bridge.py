"""Viber Event Bridge (Windows GUI). Run this file, or build it into an .exe with build.bat."""
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

import httpx

from core import find_urls, load_config, log, log_lines, save_config, webcal_link
from sender import post_link, replay_loop, toast_loop


def setup_window() -> dict | None:
    win = tk.Tk()
    win.title("Viber Event Bridge - Setup")
    result: dict = {}
    fields = {}
    rows = [("server_url", "Render URL (https://....onrender.com)"),
            ("webhook_secret", "WEBHOOK_SECRET"), ("feed_token", "FEED_TOKEN")]
    for i, (key, label) in enumerate(rows):
        tk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
        e = tk.Entry(win, width=48)
        e.grid(row=i, column=1, padx=8)
        fields[key] = e

    def save():
        cfg = {k: v.get().strip() for k, v in fields.items()}
        if not cfg["server_url"].startswith("http") or not cfg["webhook_secret"] or not cfg["feed_token"]:
            messagebox.showerror("Missing info", "Fill in all three fields.")
            return
        try:
            ok = httpx.get(cfg["server_url"].rstrip("/") + "/healthz", timeout=90).status_code == 200
        except httpx.HTTPError:
            ok = False
        if not ok and not messagebox.askyesno("Server unreachable", "Could not reach the server. Save anyway?"):
            return
        result.update(cfg)
        win.destroy()

    tk.Button(win, text="Save and start", command=save).grid(row=3, column=1, sticky="e", padx=8, pady=8)
    win.mainloop()
    if result:
        save_config(result)
    return result or None


def clipboard_loop(cfg: dict, root: tk.Tk, enabled: tk.BooleanVar, stop: threading.Event) -> None:
    seen = ""
    while not stop.wait(1.5):
        if not enabled.get():
            continue
        try:
            text = root.clipboard_get()
        except tk.TclError:
            continue
        if text != seen:
            seen = text
            if len(text) < 600:
                for u in find_urls(text):
                    post_link(cfg, u, "Copied from Viber")


def main_window(cfg: dict) -> None:
    root = tk.Tk()
    root.title("Viber Event Bridge")
    link = webcal_link(cfg)
    tk.Label(root, text="Your calendar link (open on iPhone to subscribe):").pack(anchor="w", padx=8, pady=(8, 0))
    ent = tk.Entry(root, width=70)
    ent.insert(0, link)
    ent.pack(padx=8)

    def copy():
        root.clipboard_clear()
        root.clipboard_append(link)

    tk.Button(root, text="Copy link", command=copy).pack(anchor="w", padx=8, pady=4)
    clip = tk.BooleanVar(value=False)
    tk.Checkbutton(root, text="Also capture links I copy to the clipboard (fallback)", variable=clip).pack(anchor="w", padx=8)
    box = scrolledtext.ScrolledText(root, width=80, height=14, state="disabled")
    box.pack(padx=8, pady=8)
    stop = threading.Event()
    for fn in (toast_loop, replay_loop):
        threading.Thread(target=fn, args=(cfg, stop), daemon=True).start()
    threading.Thread(target=clipboard_loop, args=(cfg, root, clip, stop), daemon=True).start()
    shown = 0

    def refresh():
        nonlocal shown
        if shown < len(log_lines):
            box.configure(state="normal")
            for line in log_lines[shown:]:
                box.insert("end", line + "\n")
            box.see("end")
            box.configure(state="disabled")
            shown = len(log_lines)
        root.after(1000, refresh)

    refresh()
    root.protocol("WM_DELETE_WINDOW", lambda: (stop.set(), root.destroy()))
    root.mainloop()


def main() -> None:
    cfg = load_config() or setup_window()
    if not cfg:
        sys.exit(0)
    log("started")
    main_window(cfg)


if __name__ == "__main__":
    main()
