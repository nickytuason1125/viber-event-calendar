"""One-shot test: OCR the Viber window and report counts only (no message text printed)."""
import screenreader as s

w = s.viber_window()
print("viber window found:", bool(w))
if w:
    img = s.capture(w)
    print("captured:", None if img is None else img.size)
    if img:
        text = s.read_text(img)
        links = s.find_links(text)
        print("ocr characters:", len(text), "lines:", text.count("\n") + 1)
        print("links found:", len(links))
        for u in links:
            print("  host:", u.split("/")[2] if "//" in u else u[:30], "| length:", len(u))
