"""Posting links to the server, replay, and background watcher loops."""
import json
import os
import threading
import time

import httpx

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
