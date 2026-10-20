"""SQLite storage. Set DB_PATH to change location (Render disk is ephemeral on free tier)."""
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "events.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    uid TEXT PRIMARY KEY, url TEXT, title TEXT, description TEXT, location TEXT,
    start TEXT, end TEXT, all_day INTEGER, shared_by TEXT, found_date INTEGER,
    sequence INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT
)"""

FIELDS = ("url", "title", "description", "location", "start", "end", "all_day", "shared_by", "found_date")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute(SCHEMA)
    return c


def upsert(evt: dict) -> None:
    """Insert, or update and bump SEQUENCE only when content changed."""
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "uid": evt["uid"], "url": evt["url"], "title": evt["title"],
        "description": evt["description"], "location": evt["location"],
        "start": evt["start"].isoformat(), "end": evt["end"].isoformat(),
        "all_day": int(evt["all_day"]), "shared_by": evt["shared_by"],
        "found_date": int(evt["found_date"]),
    }
    with _conn() as c:
        old = c.execute("SELECT * FROM events WHERE uid=?", (row["uid"],)).fetchone()
        if old is None:
            c.execute(
                "INSERT INTO events (uid,url,title,description,location,start,end,all_day,shared_by,found_date,sequence,created_at,updated_at) "
                "VALUES (:uid,:url,:title,:description,:location,:start,:end,:all_day,:shared_by,:found_date,0,:now,:now)",
                {**row, "now": now},
            )
            return
        # keep original sharer; compare the rest
        row["shared_by"] = old["shared_by"]
        if any(old[f] != row[f] for f in FIELDS):
            c.execute(
                "UPDATE events SET url=:url,title=:title,description=:description,location=:location,start=:start,end=:end,"
                "all_day=:all_day,shared_by=:shared_by,found_date=:found_date,sequence=sequence+1,updated_at=:now WHERE uid=:uid",
                {**row, "now": now},
            )


def all_events() -> list[sqlite3.Row]:
    with _conn() as c:
        return c.execute("SELECT * FROM events ORDER BY start").fetchall()
