"""Read-only probe: is Viber Desktop's viber.db plain SQLite? Prints header + schema only, no messages."""
import glob
import os
import shutil
import sqlite3
import tempfile

base = os.path.join(os.environ["APPDATA"], "ViberPC")
dbs = [p for p in glob.glob(os.path.join(base, "*", "viber.db")) if os.path.isfile(p)]
print("found:", dbs)
for src in dbs:
    tmp = tempfile.mkdtemp()
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(src + ext):
            shutil.copy2(src + ext, os.path.join(tmp, "viber.db" + ext))
    with open(os.path.join(tmp, "viber.db"), "rb") as f:
        head = f.read(16)
    print("header:", head, "-> plain SQLite" if head.startswith(b"SQLite format 3") else "-> NOT plain SQLite (likely encrypted)")
    try:
        con = sqlite3.connect(os.path.join(tmp, "viber.db"))
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        print("tables:", tables)
        for t in ("Events", "Messages", "ChatInfo", "Chat"):
            if t in tables:
                print(t, [r[1] for r in con.execute(f"PRAGMA table_info({t})")])
    except sqlite3.DatabaseError as e:
        print("cannot open:", e)
    shutil.rmtree(tmp, ignore_errors=True)
