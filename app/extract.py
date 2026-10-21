"""Deterministic (no-LLM) event extraction from a web page."""
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import dateparser
from bs4 import BeautifulSoup

TZ = ZoneInfo("Asia/Manila")
MONTHS = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
DATE_HINT = re.compile(
    rf"(\b{MONTHS}\.?\s+\d{{1,2}}\b|\b\d{{1,2}}\s+{MONTHS}\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}/\d{{1,2}}/\d{{2,4}}\b)",
    re.IGNORECASE,
)
_TIME = r"(?:\s*(?:,|at|@)?\s*(?:\d{1,2}:\d{2}(?:\s*(?:am|pm))?|\d{1,2}\s*(?:am|pm)))?"
LONG_TOKEN = re.compile(r"\S{60,}")
DATE_FULL = re.compile(
    rf"(?:\b{MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?{_TIME}"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}\.?(?:,?\s+\d{{4}})?{_TIME}"
    rf"|\b\d{{4}}-\d{{2}}-\d{{2}}(?:[T ]\d{{2}}:\d{{2}})?)",
    re.IGNORECASE,
)
VENUE_RE = re.compile(
    r"(?:Venue|Location|Where|Place|Hotel)\s*[:\-–]\s*([^\n|•]{5,100}?)(?=\s{2,}|\s(?:Date|Time|When|Register|Price)\b|[|•\n]|$)",
    re.IGNORECASE,
)


def _localize(dt: datetime) -> datetime:
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt


def parse_iso(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        return _localize(datetime.fromisoformat(v))
    except ValueError:
        d = dateparser.parse(value, settings={"TIMEZONE": "Asia/Manila", "RETURN_AS_TIMEZONE_AWARE": True})
        return d


def _is_event(node: dict) -> bool:
    t = node.get("@type", "")
    types = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and x.endswith("Event") for x in types)


def _walk(obj):
    if isinstance(obj, list):
        for i in obj:
            yield from _walk(i)
    elif isinstance(obj, dict):
        yield obj
        for key in ("@graph", "itemListElement", "item", "subEvent"):
            if key in obj:
                yield from _walk(obj[key])


def _location_text(loc) -> str | None:
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, str):
        return loc.strip() or None
    if not isinstance(loc, dict):
        return None
    parts = [loc.get("name")]
    addr = loc.get("address")
    if isinstance(addr, str):
        parts.append(addr)
    elif isinstance(addr, dict):
        parts += [addr.get("streetAddress"), addr.get("addressLocality"), addr.get("addressCountry") if isinstance(addr.get("addressCountry"), str) else None]
    parts = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    return ", ".join(dict.fromkeys(parts)) or None


def _jsonld_event(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", type=re.compile("ld\\+json", re.I)):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (ValueError, TypeError):
            continue
        for node in _walk(data):
            if _is_event(node):
                return node
    return None


def _meta(soup: BeautifulSoup, *names) -> str | None:
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content", "").strip():
            return tag["content"].strip()
    return None


def _find_date(text: str, now: datetime) -> datetime | None:
    """Only trust matches that contain an explicit month name or numeric date."""
    parsed = []
    for m in list(DATE_FULL.finditer(text))[:15]:
        snippet = re.sub(r"\s+(at|@|,)\s+", " ", m.group(0).strip(), flags=re.IGNORECASE)
        d = dateparser.parse(
            snippet,
            languages=["en"],
            settings={"PREFER_DATES_FROM": "future", "TIMEZONE": "Asia/Manila", "RETURN_AS_TIMEZONE_AWARE": True, "RELATIVE_BASE": now},
        )
        if d:
            parsed.append(d)
    if not parsed:
        return None
    upcoming = [d for d in parsed if d >= now - timedelta(days=1)]
    return (upcoming or parsed)[0]


def extract_event(html: str, url: str, now: datetime | None = None) -> dict:
    """Return dict(title, description, location, start, end, all_day, found_date)."""
    now = now or datetime.now(TZ)
    soup = BeautifulSoup(html or "", "html.parser")
    title = description = location = None
    start = end = None

    ev = _jsonld_event(soup)
    if ev:
        title = ev.get("name")
        description = ev.get("description")
        location = _location_text(ev.get("location"))
        start = parse_iso(ev.get("startDate"))
        end = parse_iso(ev.get("endDate"))

    title = title or _meta(soup, "og:title", "twitter:title") or (soup.title.get_text(strip=True) if soup.title else None) or url
    description = description or _meta(soup, "og:description", "description", "twitter:description") or ""

    if not start:
        t = soup.find("time", attrs={"datetime": True})
        if t:
            start = parse_iso(t["datetime"])

    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    headings = " ".join(h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])[:8])
    # drop long encoded blobs (base64/JSON) that some CMS pages embed, then scan the readable text
    body = LONG_TOKEN.sub(" ", " ".join(soup.stripped_strings))[:20000]

    if not start:
        for chunk in (title, description, headings, body):
            start = _find_date(chunk, now)
            if start:
                break

    if not location:
        for chunk in (body, headings):
            m = VENUE_RE.search(chunk)
            if m:
                location = m.group(1).strip(" ,.-")
                break
        if not location:
            el = soup.find(class_=re.compile(r"venue|location", re.I))
            if el and el.get_text(strip=True):
                location = el.get_text(" ", strip=True)[:120]

    found_date = start is not None
    all_day = False
    if not start:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        all_day = True
        title = f"[Date TBC] {title}"
    elif not end or end <= start:
        end = start + timedelta(hours=3)

    return {
        "title": " ".join(str(title).split())[:200],
        "description": " ".join(str(description).split())[:700],
        "location": location or "See event link for venue",
        "start": start,
        "end": end,
        "all_day": all_day,
        "found_date": found_date,
    }
