# Viber GC Event Bulletin

Links shared in a Viber group chat become events in an iPhone calendar, with a "what / where / when" description and alerts. No LLM: dates and venues come from the page's own metadata (JSON-LD, OpenGraph, `<time>`, text heuristics).

```
Viber Desktop (Windows) -> ViberEventBridge.exe -> Render server -> /calendar.ics -> iPhone Calendar
```

## Setup (about 10 minutes)

### 1. Put the server on Render
1. Push this folder to a new GitHub repo (`git init`, `git add .`, `git commit`, then push).
2. In Render: **New > Blueprint**, select the repo, and click **Apply**. `render.yaml` creates the service and generates `WEBHOOK_SECRET` and `FEED_TOKEN`.
3. In the service's **Environment** tab, copy both values. The URL looks like `https://viber-event-calendar.onrender.com`.

### 2. Build and run the Windows bridge
1. Double-click `bridge\build.bat`. It produces `dist\ViberEventBridge.exe`. (Or run `python bridge\bridge.py`.)
2. Start the exe and enter the Render URL, `WEBHOOK_SECRET` and `FEED_TOKEN`.
3. In Viber Desktop, keep notifications on for the group chat. Keep Windows Focus Assist off.
4. Optional: press Win+R, type `shell:startup`, and put a shortcut to the exe there.

### 3. Subscribe on iPhone
Copy the calendar link from the bridge window and open it on the iPhone (AirDrop, Notes or Messages), then tap **Subscribe**. Then go to Settings > Calendar > Accounts > Subscribed Calendars and set a short fetch interval. Check that Calendar notifications are enabled.

## Other ways to add links
- Tick **Also capture links I copy** in the bridge window. Copying a link in Viber sends it.
- Open `https://YOUR-APP.onrender.com/add?token=FEED_TOKEN` in any browser and paste a link.
- iPhone Shortcut: a "Get Contents of URL" action doing POST to `/webhook/viber-link` with header `X-Webhook-Secret` and JSON body `{"url": <Shortcut Input>, "sender": "iPhone"}`, added to the share sheet.

## Limits (please read)
- **Toast capture is unverified against live Viber toasts.** I confirmed the Windows notification database exists and is readable on this PC, but there were no Viber entries in it yet. Test it: post a link in your GC and watch the bridge log. If nothing appears, use the clipboard or `/add` options.
- Toasts may cut off long links. A cut-off link will fail to scrape.
- **Render free tier** sleeps after about 15 minutes idle, so the first request can take a minute. The server's disk is wiped on restart, so the bridge re-sends all saved links every 6 hours and on startup. The feed can be empty until then. For durable storage, use a paid Render disk and set `DB_PATH` to it.
- If the page has no readable date, the event is added as an all-day "[Date TBC]" item with the link.
- Some sites block cloud servers or need JavaScript (Facebook, Instagram). Those fall back to a basic entry.
- The PC must be on, with Viber Desktop running and the GC unmuted.
- The .exe is not code-signed, so Windows SmartScreen may warn.

## Develop
```
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
pytest
python tests\live_check.py
uvicorn app.main:app --reload
```
Environment variables: `WEBHOOK_SECRET`, `FEED_TOKEN`, `DB_PATH`.
