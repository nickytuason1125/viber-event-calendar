"""Build the .ics feed with two display alarms per event."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from icalendar import Alarm, Calendar, Event

TZ = ZoneInfo("Asia/Manila")


def build_feed(rows, now: datetime | None = None) -> bytes:
    now = now or datetime.now(timezone.utc)
    cal = Calendar()
    cal.add("prodid", "-//Viber GC Event Bulletin//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", "Viber GC Events")
    cal.add("x-wr-timezone", "Asia/Manila")
    cal.add("refresh-interval;value=duration", "PT1H")
    cal.add("x-published-ttl", "PT1H")

    for r in rows:
        start = datetime.fromisoformat(r["start"]).astimezone(TZ)
        end = datetime.fromisoformat(r["end"]).astimezone(TZ)
        ev = Event()
        ev.add("uid", r["uid"])
        ev.add("dtstamp", datetime.fromisoformat(r["updated_at"]))
        ev.add("sequence", r["sequence"])
        ev.add("summary", r["title"])
        if r["all_day"]:
            ev.add("dtstart", start.date())
            ev.add("dtend", end.date())
        else:
            ev.add("dtstart", start)
            ev.add("dtend", end)
        ev.add("location", r["location"])
        ev.add("url", r["url"])
        ev.add("transp", "TRANSPARENT")
        desc = (
            f"WHAT IT IS:\n{r['description'] or 'No description provided.'}\n\n"
            f"WHERE:\n{r['location']}\n\n"
            f"SHARED BY: {r['shared_by']} in Viber GC\n"
            f"LINK: {r['url']}"
        )
        if not r["found_date"]:
            desc = "DATE NOT FOUND ON PAGE - check the link.\n\n" + desc
        ev.add("description", desc)

        if r["all_day"]:
            alarms = [("Date TBC: " + r["title"], timedelta(hours=9))]  # 9 AM on the day
        else:
            alarms = [
                (f"Tomorrow: {r['title']}", timedelta(days=-1)),
                (f"In 2 hours: {r['title']} @ {r['location']}", timedelta(hours=-2)),
            ]
        for text, trig in alarms:
            fire = (datetime.combine(start.date(), datetime.min.time(), TZ) + trig) if r["all_day"] else start + trig
            if fire.astimezone(timezone.utc) < now:
                continue
            a = Alarm()
            a.add("action", "DISPLAY")
            a.add("description", text)
            a.add("trigger", trig, parameters={"RELATED": "START"} if not r["all_day"] else None)
            ev.add_component(a)
        cal.add_component(ev)
    return cal.to_ical()
