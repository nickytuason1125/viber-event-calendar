"""Viber Event Bridge core logic (no GUI): toast reading, posting, replay."""
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import xml.etree.ElementTree as ET

import httpx

APP_DIR = os.path.join(os.environ.get("APPDATA", "."), "ViberEventBridge")
CONFIG = os.path.join(APP_DIR, "config.json")
SENT = os.path.join(APP_DIR, "sent_links.jsonl")
WPN_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Notifications")
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
POLL_SECONDS = 3
REPLAY_SECONDS = 6 * 3600

log_lines: list[str] = []


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')}  {msg}"
    log_lines.append(line)
    print(line, flush=True)


def load_config() -> dict | None:
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_config(cfg: dict) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f)


def webcal_link(cfg: dict) -> str:
    host = re.sub(r"^https?://", "", cfg["server_url"].rstrip("/"))
    return f"webcal://{host}/calendar.ics?token={cfg['feed_token']}"


def find_urls(text: str) -> list[str]:
    return list(dict.fromkeys(m.rstrip(".,;:!?)") for m in URL_RE.findall(text or "")))


def parse_toast_payload(payload) -> tuple[str, str]:
    """Return (title, body) from a toast XML payload."""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace").lstrip("\ufeff\x00")
    try:
        texts = [(t.text or "").strip() for t in ET.fromstring(payload).iter("text")]
    except ET.ParseError:
        return "", str(payload)
    texts = [t for t in texts if t]
    return (texts[0] if texts else ""), " ".join(texts[1:])


def _snapshot_db() -> str:
    tmp = tempfile.mkdtemp()
    for name in ("wpndatabase.db", "wpndatabase.db-wal", "wpndatabase.db-shm"):
        p = os.path.join(WPN_DIR, name)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(tmp, name))
    return tmp


def read_viber_toasts(last_id: int) -> list[tuple[int, str, str]]:
    """New Viber toasts as (id, title, body), read from a copy of the notification DB."""
    tmp = ""
    try:
        tmp = _snapshot_db()
        con = sqlite3.connect(os.path.join(tmp, "wpndatabase.db"))
        rows = con.execute(
            "SELECT n.Id, n.Payload FROM Notification n JOIN NotificationHandler h ON n.HandlerId=h.RecordId "
            "WHERE LOWER(h.PrimaryId) LIKE '%viber%' AND n.Id > ? ORDER BY n.Id", (last_id,)).fetchall()
        con.close()
        return [(i, *parse_toast_payload(p)) for i, p in rows]
    except (sqlite3.Error, OSError):
        return []
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def max_toast_id() -> int:
    tmp = ""
    try:
        tmp = _snapshot_db()
        con = sqlite3.connect(os.path.join(tmp, "wpndatabase.db"))
        v = con.execute("SELECT COALESCE(MAX(Id),0) FROM Notification").fetchone()[0]
        con.close()
        return v
    except (sqlite3.Error, OSError):
        return 0
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
