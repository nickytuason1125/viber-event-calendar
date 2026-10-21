"""Run everything locally: server on this PC + bridge config. Usage: python local.py"""
import json
import os
import secrets
import socket
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(ROOT, "local_config.json")
BRIDGE_DIR = os.path.join(os.environ.get("APPDATA", "."), "ViberEventBridge")
PORT = 8000


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packets sent; just picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def load_cfg() -> dict:
    if os.path.exists(CFG_PATH):
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    cfg = {"webhook_secret": secrets.token_hex(16), "feed_token": secrets.token_hex(16)}
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    return cfg


def main() -> None:
    cfg = load_cfg()
    ip = lan_ip()
    os.makedirs(BRIDGE_DIR, exist_ok=True)
    with open(os.path.join(BRIDGE_DIR, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"server_url": f"http://127.0.0.1:{PORT}", "public_url": f"http://{ip}:{PORT}",
                   "webhook_secret": cfg["webhook_secret"], "feed_token": cfg["feed_token"]}, f)
    print(f"Calendar link for iPhone (same Wi-Fi): webcal://{ip}:{PORT}/calendar.ics?token={cfg['feed_token']}")
    print("Leave this window open. Ctrl+C to stop.")
    env = dict(os.environ, WEBHOOK_SECRET=cfg["webhook_secret"], FEED_TOKEN=cfg["feed_token"],
               DB_PATH=os.path.join(ROOT, "events.db"))
    subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(PORT)],
                   cwd=ROOT, env=env)


if __name__ == "__main__":
    main()
