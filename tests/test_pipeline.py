import os
import tempfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["WEBHOOK_SECRET"] = "sek"
os.environ["FEED_TOKEN"] = "tok"

from fastapi.testclient import TestClient
from icalendar import Calendar

from app import db, main
from app.extract import extract_event
from app.ical import build_feed
from app.urls import clean_url, extract_urls, is_safe_url, uid_for

MNL = ZoneInfo("Asia/Manila")
NOW = datetime(2026, 10, 21, 9, 0, tzinfo=MNL)

JSONLD = """<html><head><title>x</title><script type="application/ld+json">
{"@graph":[{"@type":["Event","EducationEvent"],"name":"Access MBA Manila",
"startDate":"2026-11-10T16:00:00+08:00","endDate":"2026-11-10T20:45:00+08:00",
"location":{"@type":"Place","name":"Dusit Thani Manila","address":"Ayala Center, Makati"},
"description":"MBA fair"}]}</script></head><body></body></html>"""

OG_ONLY = """<html><head><title>T</title><meta property="og:title" content="Tech Meetup">
<meta property="og:description" content="Talks and pizza."></head>
<body><h1>Tech Meetup</h1><p>Date: November 14, 2026 at 6:00 PM</p><p>Venue: Co-Working Hub, BGC  </p></body></html>"""

PLAIN = "<html><head><title>Blog</title></head><body><p>It may rain now and today.</p></body></html>"


def test_clean_url_keeps_meaningful_params():
    u = "https://www.accessmba.com/events/page/manila/?utm_source=fb&fbclid=1&ui=ABC&id=5#x"
    assert clean_url(u) == "https://www.accessmba.com/events/page/manila?id=5"
    assert uid_for(u) == uid_for("https://www.accessmba.com/events/page/manila?id=5")
    assert uid_for("https://a.com/e?id=1") != uid_for("https://a.com/e?id=2")


def test_extract_urls_strips_punctuation():
    assert extract_urls("see https://a.com/x), and https://b.com.") == ["https://a.com/x", "https://b.com"]


def test_ssrf_blocked():
    assert not is_safe_url("http://127.0.0.1/")
    assert not is_safe_url("http://localhost:8000/")
    assert not is_safe_url("http://169.254.169.254/latest")
    assert not is_safe_url("file:///etc/passwd")


def test_jsonld_graph_and_list_type():
    e = extract_event(JSONLD, "https://x.com/e", NOW)
    assert e["title"] == "Access MBA Manila"
    assert e["start"].isoformat() == "2026-11-10T16:00:00+08:00"
    assert "Dusit Thani Manila" in e["location"] and "Makati" in e["location"]
    assert e["found_date"]


def test_og_and_heuristics():
    e = extract_event(OG_ONLY, "https://x.com/e", NOW)
    assert e["title"] == "Tech Meetup" and e["description"] == "Talks and pizza."
    assert (e["start"].month, e["start"].day, e["start"].hour) == (11, 14, 18)
    assert e["location"].startswith("Co-Working Hub")


def test_no_false_date_from_words():
    e = extract_event(PLAIN, "https://x.com/e", NOW)
    assert not e["found_date"] and e["all_day"] and e["title"].startswith("[Date TBC]")


def _evt(title="A", loc="L"):
    e = extract_event(JSONLD, "https://x.com/e", NOW)
    e.update({"uid": "u1@t", "url": "https://x.com/e", "shared_by": "Jisac", "title": title, "location": loc})
    return e


def test_upsert_sequence_and_feed_roundtrip():
    db.upsert(_evt())
    db.upsert(_evt())
    assert db.all_events()[0]["sequence"] == 0
    db.upsert(_evt(loc="New Venue"))
    rows = db.all_events()
    assert len(rows) == 1 and rows[0]["sequence"] == 1
    cal = Calendar.from_ical(build_feed(rows, now=datetime(2026, 10, 21, tzinfo=timezone.utc)))
    ev = cal.walk("VEVENT")[0]
    assert str(ev["TRANSP"]) == "TRANSPARENT" and ev["SEQUENCE"] == 1
    assert "DTSTAMP" in ev and str(ev["LOCATION"]) == "New Venue"
    assert len(ev.walk("VALARM")) == 2


def test_api_auth_and_feed():
    c = TestClient(main.app)
    assert c.post("/webhook/viber-link", json={"url": "https://a.com"}).status_code == 401
    r = c.post("/webhook/viber-link", headers={"X-Webhook-Secret": "sek"}, json={"sender": "J", "text": "no links"})
    assert r.json()["count"] == 0
    assert c.get("/calendar.ics").status_code == 401
    r = c.get("/calendar.ics?token=tok")
    assert r.status_code == 200 and b"BEGIN:VCALENDAR" in r.content
