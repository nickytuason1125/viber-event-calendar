"""Live end-to-end check: local event page -> webhook -> feed. Run: python tests/live_check.py"""
import http.server
import os
import tempfile
import threading

os.environ.update(DB_PATH=os.path.join(tempfile.mkdtemp(), "live.db"), WEBHOOK_SECRET="s", FEED_TOKEN="t")
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from icalendar import Calendar

from app import fetch, main, urls

PAGE = b"""<html><head><title>Access MBA One-to-One Event in Manila</title>
<meta name="description" content="Meet MBA admissions directors one-to-one."></head>
<body><h1>Manila</h1><p>Tuesday, November 10, 2026 4:00 PM</p><p>Venue: Dusit Thani Manila, Makati  </p></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]

# SSRF guard is verified in unit tests; allow loopback only for this local demo page.
orig = urls.is_safe_url
allow = lambda u: True if f"127.0.0.1:{port}" in u else orig(u)
fetch.is_safe_url = allow
main.is_safe_url = allow

c = TestClient(main.app)
url = f"http://127.0.0.1:{port}/events/page/manila?utm_source=facebook&fbclid=abc&ui=XYZ"
r = c.post("/webhook/viber-link", headers={"X-Webhook-Secret": "s"}, json={"sender": "Jisac Palacio", "text": f"look {url}"})
print("webhook:", r.json())
feed = c.get("/calendar.ics?token=t").content
print(feed.decode())
ev = Calendar.from_ical(feed).walk("VEVENT")[0]
assert str(ev["SUMMARY"]).startswith("Access MBA")
assert "Dusit Thani" in str(ev["LOCATION"])
assert ev["DTSTART"].dt.isoformat().startswith("2026-11-10T16:00")
assert "utm_" not in str(ev["URL"])
print("LIVE CHECK OK")
