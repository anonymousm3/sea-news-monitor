import json
import os
from pathlib import Path

import requests

URL = "https://sea-news.combocabal.com/"
DATE_TO_WATCH = "19-03-2026"
STATE_FILE = Path("state.json")
TIMEOUT = 20


def fetch_page():
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SEA-News-Date-Monitor/1.0)"
    }
    r = requests.get(URL, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"found_before": False}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8"
    )


def send_discord(message: str):
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    r = requests.post(webhook_url, json={"content": message}, timeout=TIMEOUT)
    r.raise_for_status()


def main():
    html = fetch_page()
    found_now = DATE_TO_WATCH in html

    old_state = load_state()
    found_before = old_state.get("found_before", False)

    if found_now and not found_before:
        send_discord(
            f"🚨 Date detected on SEA news page: {DATE_TO_WATCH}\n{URL}"
        )
        print(f"Detected {DATE_TO_WATCH}. Discord notification sent.")
    elif found_now:
        print(f"{DATE_TO_WATCH} is present, but already alerted before.")
    else:
        print(f"{DATE_TO_WATCH} not found.")

    save_state({"found_before": found_now})


if __name__ == "__main__":
    main()
