"""Safe page fetching: SSRF checks on every redirect hop, timeout and size cap."""
from urllib.parse import urljoin

import httpx

from .urls import is_safe_url

MAX_BYTES = 2_000_000
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36", "Accept-Language": "en"}


def fetch_html(url: str, max_redirects: int = 4) -> str | None:
    """Return page HTML, or None if blocked/unreachable."""
    current = url
    try:
        with httpx.Client(timeout=10, headers=HEADERS, follow_redirects=False) as client:
            for _ in range(max_redirects + 1):
                if not is_safe_url(current):
                    return None
                with client.stream("GET", current) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                        current = urljoin(current, resp.headers["location"])
                        continue
                    if resp.status_code >= 400:
                        return None
                    buf = b""
                    for chunk in resp.iter_bytes():
                        buf += chunk
                        if len(buf) > MAX_BYTES:
                            break
                    return buf.decode(resp.encoding or "utf-8", errors="replace")
    except httpx.HTTPError:
        return None
    return None
