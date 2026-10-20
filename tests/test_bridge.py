import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bridge"))
from core import find_urls, parse_toast_payload, webcal_link  # noqa: E402

TOAST = b'<toast><visual><binding template="ToastGeneric"><text>Jisac Palacio</text><text>Check https://www.accessmba.com/events/page/manila?utm_source=fb</text></binding></visual></toast>'


def test_parse_toast():
    title, body = parse_toast_payload(TOAST)
    assert title == "Jisac Palacio" and "accessmba.com" in body


def test_webcal():
    cfg = {"server_url": "https://x.onrender.com/", "feed_token": "t"}
    assert webcal_link(cfg) == "webcal://x.onrender.com/calendar.ics?token=t"
