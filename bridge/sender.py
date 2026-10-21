"""Posting links to the server, replay, and background watcher loops."""
import json
import os
import threading
import time

import httpx

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import APP_DIR, REPLAY_SECONDS, POLL_SECONDS, SENT, find_urls, log, max_toast_id, read_viber_toasts


def post_link(cfg: dict, url: str, sender: str, record: bool = True) -> bool:
    """POST with a long timeout (Render free tier cold-starts) and retries."""
    endpoint = cfg["server_url"].rstrip("/") + "/webhook/viber-link"
    for attempt in range(3):
        try:
            r = httpx.post(endpoint, json={"url": url, "sender": sender},
                           headers={"X-Webhook-Secret": cfg["webhook_secret"]}, timeout=90)
            if r.status_code == 200:
                log(f"sent: {url}")
                if record:
                    os.makedirs(APP_DIR, exist_ok=True)
                    with open(SENT, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"url": url, "sender": sender}) + "\n")
                return True
            log(f"server said {r.status_code} for {url}")
            if r.status_code == 401:
                log("check WEBHOOK_SECRET in setup")
                return False
        except httpx.HTTPError as e:
            log(f"network error ({type(e).__name__}); retry {attempt + 1}/3")
        time.sleep(5)
    return False


def replay_all(cfg: dict) -> None:
    """Re-send saved links so a Render restart (wiped disk) does not empty the feed."""
    try:
        with open(SENT, encoding="utf-8") as f:
            items = {}
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    items[d["url"]] = d
    except (OSError, ValueError, KeyError):
        return
    if items:
        log(f"replaying {len(items)} saved link(s)")
    for it in items.values():
        post_link(cfg, it["url"], it["sender"], record=False)


def toast_loop(cfg: dict, stop: threading.Event) -> None:
    last = max_toast_id()
    log("toast watcher on: waiting for new Viber notifications")
    while not stop.wait(POLL_SECONDS):
        for nid, title, body in read_viber_toasts(last):
            last = max(last, nid)
            for u in find_urls(body):
                post_link(cfg, u, title or "Viber GC")


def replay_loop(cfg: dict, stop: threading.Event) -> None:
    replay_all(cfg)
    while not stop.wait(REPLAY_SECONDS):
        replay_all(cfg)


def _already_sent() -> set:
    try:
        with open(SENT, encoding="utf-8") as f:
            return {json.loads(line)["url"] for line in f if line.strip()}
    except (OSError, ValueError, KeyError):
        return set()


def link_loads(url: str) -> bool:
    """OCR can misread characters; only forward links that actually load."""
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        return r.status_code < 400
    except httpx.HTTPError:
        return False


def screen_loop(cfg: dict, stop: threading.Event, enabled=None, chats=None, interval: float = 6.0) -> None:
    """Read links from the open chat, only if it is one of the allowed group chats."""
    try:
        import screenreader
    except Exception as e:  # winrt/uiautomation missing
        log(f"screen reader unavailable: {type(e).__name__}")
        return
    seen = _already_sent()
    rejected: set = set()
    warned: list = []
    log("screen watcher on: reads only your 2 chosen group chats")
    while not stop.wait(interval):
        if enabled is not None and not enabled():
            continue
        try:
            win = screenreader.viber_window()
            img = screenreader.capture(win) if win else None
            if img is None:
                continue
            allowed = [c.strip() for c in (chats() if chats else "").split(",") if c.strip()][:2]
            if not allowed:
                if not warned:
                    log("no group chat names set: type your 2 chat names in the box, then press Save")
                    warned.append(1)
                continue
            header_img, body_img = screenreader.split_chat_pane(img)
            chat = screenreader.matches_chat(screenreader.read_text(header_img), allowed)
            if not chat:
                continue  # some other chat is open: ignore it
            links = screenreader.find_links(screenreader.read_text(body_img))
        except Exception as e:
            log(f"screen read error: {type(e).__name__}")
            continue
        for u in links:
            if u in seen or u in rejected:
                continue
            if not link_loads(u):
                rejected.add(u)
                log(f"skipped (does not load, maybe misread): {u}")
                continue
            if post_link(cfg, u, chat):
                seen.add(u)
