import json
import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://sea-news.combocabal.com/"
STATE_FILE = Path("state.json")
TIMEOUT = 20


def fetch_page():
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SEA-News-Monitor/1.0)"
    }
    r = requests.get(URL, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def clean_text(text: str) -> str:
    return " ".join(text.split()).strip()


def looks_like_date(text: str) -> bool:
    text = clean_text(text)
    patterns = [
        r"\b\d{2}-\d{2}-\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
    ]
    return any(re.search(p, text) for p in patterns)


def extract_news_items(html: str):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    items = []

    containers = soup.select("article, .news, .post, .entry, .article, .item, li, .card, main div")

    for container in containers:
        texts = [
            clean_text(t.get_text(" ", strip=True))
            for t in container.find_all(["h1", "h2", "h3", "h4", "p", "span", "a", "div"])
        ]
        texts = [t for t in texts if t and t.lower() != "please follow new news coming soon."]

        if not texts:
            continue

        date_text = None
        title_text = None

        for t in texts:
            if looks_like_date(t):
                date_text = t
                break

        for t in texts:
            if not looks_like_date(t) and len(t) >= 4:
                title_text = t
                break

        if date_text or title_text:
            key = f"{date_text or ''} | {title_text or ''}".strip()
            items.append({
                "date": date_text or "",
                "title": title_text or "",
                "key": key
            })

    seen = set()
    filtered = []

    for item in items:
        key = item["key"]
        if key in seen:
            continue
        if key == "|" or key == "":
            continue
        if item["title"].lower() == "please follow new news coming soon.":
            continue
        seen.add(key)
        filtered.append(item)

    return filtered


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"items": []}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def send_discord(message: str):
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    payload = {"content": message[:1900]}
    r = requests.post(webhook_url, json=payload, timeout=TIMEOUT)
    r.raise_for_status()


def main():
    html = fetch_page()
    current_items = extract_news_items(html)

    old_state = load_state()
    old_keys = {item["key"] for item in old_state.get("items", [])}
    new_items = [item for item in current_items if item["key"] not in old_keys]

    if not STATE_FILE.exists():
        save_state({"items": current_items})
        print("Initial snapshot saved. No notification sent.")
        print(current_items)
        return

    if new_items:
        lines = []
        for item in new_items:
            if item["date"] and item["title"]:
                lines.append(f"• {item['date']} — {item['title']}")
            elif item["title"]:
                lines.append(f"• {item['title']}")
            elif item["date"]:
                lines.append(f"• {item['date']}")

        msg = (
            "🚨 **New SEA Combo Cabal update detected**\n"
            f"{URL}\n\n" +
            "\n".join(lines)
        )
        send_discord(msg)
        print("New update detected. Discord notification sent.")
    else:
        print("No new updates detected.")

    save_state({"items": current_items})


if __name__ == "__main__":
    main()
