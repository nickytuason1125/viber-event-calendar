"""URL extraction, tracking-parameter stripping and SSRF protection."""
import hashlib
import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
TRAILING = ".,;:!?)]}>"

TRACKING_KEYS = {
    "fbclid", "gclid", "dclid", "msclkid", "yclid", "igshid", "igsh", "ui",
    "mc_cid", "mc_eid", "_hsenc", "_hsmi", "si", "ref_src", "spm",
}


def extract_urls(text: str) -> list[str]:
    """Return unique URLs found in free text, in order."""
    seen, out = set(), []
    for raw in URL_RE.findall(text or ""):
        url = raw.rstrip(TRAILING)
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _is_tracking(key: str) -> bool:
    k = key.lower()
    return k.startswith("utm_") or k in TRACKING_KEYS


def utm_hints(url: str) -> dict:
    """Tracking params are dropped from the canonical URL; keep utm_* as hints."""
    q = parse_qsl(urlparse(url).query, keep_blank_values=True)
    return {k: v for k, v in q if k.lower().startswith("utm_")}


def clean_url(url: str) -> str:
    """Canonical URL: strip tracking params and fragment, keep meaningful params."""
    p = urlparse(url.strip())
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not _is_tracking(k)]
    query.sort()
    path = p.path if p.path else "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(query), ""))


def uid_for(url: str) -> str:
    return hashlib.sha1(clean_url(url).encode()).hexdigest()[:24] + "@viber-bulletin"


def is_safe_url(url: str) -> bool:
    """Reject non-http(s) URLs and hosts resolving to private/loopback/link-local IPs."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            return False
    return True
