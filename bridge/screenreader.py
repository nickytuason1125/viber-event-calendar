"""Screen reader: screenshot the Viber window and OCR it with Windows' built-in engine."""
import asyncio
import io
import re

import uiautomation as auto
from PIL import ImageGrab
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.I)
_engine = OcrEngine.try_create_from_user_profile_languages()


def viber_window():
    w = auto.WindowControl(searchDepth=1, Name="Rakuten Viber")
    return w if w.Exists(0, 0) else None


def capture(win):
    """Return a PIL image of the Viber window, or None if it is minimized/unavailable."""
    r = win.BoundingRectangle
    if r.width() < 200 or r.height() < 200 or r.left < -10000:
        return None
    return ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True)


async def _ocr(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(buf.getvalue())
    await writer.store_async()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    result = await _engine.recognize_async(bitmap)
    return "\n".join(line.text for line in result.lines)


def read_text(img) -> str:
    return asyncio.run(_ocr(img))


SIDEBAR_FRACTION = 0.34  # left part of the window is the chat list
HEADER_FRACTION = 0.14   # top strip of the chat pane holds the chat name


def split_chat_pane(img):
    """Return (header_img, body_img) of the open chat, excluding the sidebar chat list."""
    w, h = img.size
    x0 = int(w * SIDEBAR_FRACTION)
    return img.crop((x0, 0, w, int(h * HEADER_FRACTION))), img.crop((x0, int(h * HEADER_FRACTION), w, h))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def matches_chat(header_text: str, allowed: list[str], threshold: float = 0.82) -> str | None:
    """Return the allowed chat name found in the header text (fuzzy, OCR-tolerant), else None."""
    from difflib import SequenceMatcher
    lines = [_norm(x) for x in header_text.splitlines() if x.strip()]
    for name in allowed:
        n = _norm(name)
        if not n:
            continue
        for ln in lines:
            if n in ln or SequenceMatcher(None, n, ln).ratio() >= threshold:
                return name
    return None


def find_links(text: str) -> list[str]:
    """OCR often splits long links across lines; rejoin a line ending in a path/query piece."""
    joined = re.sub(r"(?<=[/\-_=&?.])\n(?=\S)", "", text)
    out = []
    for m in URL_RE.findall(joined):
        u = m.rstrip(".,;:!?)")
        if u.lower().startswith("www."):
            u = "https://" + u
        if u not in out:
            out.append(u)
    return out
