"""FastAPI server: webhook in, .ics feed out."""
import hmac
import json
import os
import re
from datetime import datetime
from urllib.parse import parse_qs

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from . import db
from .extract import TZ, extract_event
from .fetch import fetch_html
from .ical import build_feed
from .urls import clean_url, extract_urls, is_safe_url, uid_for

app = FastAPI(title="Viber GC Event Bulletin")


def _secret(name: str) -> str:
    return os.environ.get(name, "")


def _check(provided: str | None, name: str) -> None:
    expected = _secret(name)
    if not expected or not hmac.compare_digest(provided or "", expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def process_url(url: str, sender: str) -> None:
    """Scrape one URL and upsert it. Falls back to a stub event if the page can't be read."""
    clean = clean_url(url)
    if not is_safe_url(clean):
        return
    html = fetch_html(clean)
    evt = extract_event(html or "", clean)
    if not html:
        evt["title"] = f"[Date TBC] Link shared by {sender}"
        evt["description"] = "The page could not be read (blocked or offline). Open the link for details."
    evt.update({"uid": uid_for(clean), "url": clean, "shared_by": sender or "Viber GC"})
    db.upsert(evt)


async def _parse_body(req: Request) -> dict:
    raw = (await req.body()).decode("utf-8", errors="replace")
    ctype = req.headers.get("content-type", "")
    if "json" in ctype or raw.lstrip().startswith("{"):
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {"text": raw}
        except ValueError:
            # Tasker often sends unescaped quotes; salvage with regex
            m_text = re.search(r'"text"\s*:\s*"(.*)"\s*[,}]?', raw, re.S)
            m_sender = re.search(r'"sender"\s*:\s*"(.*?)"\s*,', raw, re.S)
            return {"text": m_text.group(1) if m_text else raw, "sender": m_sender.group(1) if m_sender else ""}
    if "form" in ctype:
        return {k: v[0] for k, v in parse_qs(raw).items()}
    return {"text": raw}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/webhook/viber-link")
async def webhook(req: Request, bg: BackgroundTasks, x_webhook_secret: str | None = Header(default=None)):
    _check(x_webhook_secret, "WEBHOOK_SECRET")
    data = await _parse_body(req)
    text = " ".join(str(data.get(k, "")) for k in ("url", "text"))
    sender = str(data.get("sender", "") or "Viber GC")
    urls = extract_urls(text)
    for u in urls:
        bg.add_task(process_url, u, sender)
    return {"status": "queued", "count": len(urls)}


@app.get("/calendar.ics")
def feed(token: str | None = None):
    _check(token, "FEED_TOKEN")
    body = build_feed(db.all_events())
    return Response(content=body, media_type="text/calendar; charset=utf-8",
                    headers={"Cache-Control": "no-cache", "Content-Disposition": 'inline; filename="viber-events.ics"'})


@app.get("/add", response_class=HTMLResponse)
def add_form(token: str | None = None):
    _check(token, "FEED_TOKEN")
    return f"""<!doctype html><meta name=viewport content="width=device-width">
<h3>Add an event link</h3>
<form method=post action="/add?token={token}">
<input name=url size=50 placeholder="https://..." required>
<input name=sender placeholder="Shared by (optional)">
<button>Add</button></form>"""


@app.post("/add", response_class=HTMLResponse)
async def add_submit(req: Request, bg: BackgroundTasks, token: str | None = None):
    _check(token, "FEED_TOKEN")
    data = await _parse_body(req)
    urls = extract_urls(str(data.get("url", "")))
    for u in urls:
        bg.add_task(process_url, u, str(data.get("sender") or "Viber GC"))
    return f"<p>Queued {len(urls)} link(s). Refresh your calendar in a minute.</p><a href='/add?token={token}'>Add another</a>"
