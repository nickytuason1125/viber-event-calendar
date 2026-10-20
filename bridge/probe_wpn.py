"""Read-only probe: does the Windows notification DB contain Viber toasts? Prints counts only."""
import os
import shutil
import sqlite3
import tempfile

src_dir = os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Windows", "Notifications")
tmp = tempfile.mkdtemp()
for name in ("wpndatabase.db", "wpndatabase.db-wal", "wpndatabase.db-shm"):
    p = os.path.join(src_dir, name)
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(tmp, name))
c = sqlite3.connect(os.path.join(tmp, "wpndatabase.db"))
for t in ("Notification", "NotificationHandler"):
    print(t, [r[1] for r in c.execute(f"PRAGMA table_info({t})")])
q = ("SELECT h.RecordId, h.PrimaryId, COUNT(n.Id) FROM NotificationHandler h "
     "LEFT JOIN Notification n ON n.HandlerId = h.RecordId GROUP BY h.RecordId")
for rid, pid, cnt in c.execute(q):
    if "viber" in (pid or "").lower() or cnt:
        print(rid, pid, cnt)
