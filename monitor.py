import json
import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://sea-news.combocabal.com/"
STATE_FILE = Path("state.json")
TIMEOUT = 20

BLOCKED_TITLES = {
    "home",
    "news",
    "event",
    "download",
    "reward",
    "top-up",
    "top up",
    "login",
    "register",
    "en",
    "id",
    "en id",
    "please follow new news coming soon.",
    "please follow new news coming soon",
}


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
        r"\b\d{2}-\d{2}-\d{4}\b",   # 19-03-2026
        r"\b\d{4}-\d{2}-\d{2}\b",   # 2026-03-19
        r"\b\d{2}/\d{2}/\d{4}\b",   # 19/03/2026
    ]
    return any(re.search(p, text) for p in patterns)


def looks_like_real_title(text: str) -> bool:
    t = clean_text(text)
    if not t:
        return False

    low = t.lower()

    if low in BLOCKED_TITLES:
        return False

    if looks_like_date(t):
        return False

    if len(t) < 6:
        return False

    return True


def extract_news_items(html: str):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    items = []

    # First pass: look for containers that include a date
    candidate_containers = soup.find_all(["article", "div", "li", "section"])

    for container in candidate_containers:
        container_text = clean_text(container.get_text(" ", strip=True))
        if not container_text:
            continue

        if "please follow new news coming soon" in container_text.lower():
            continue

        date_match = re.search(r"\b\d{2}-\d{2}-\d{4}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b", container_text)
        if not date_match:
            continue

        date_text = date_match.group(0)

        title_text = None

        # Prefer headings / anchors inside the same container
        for el in container.find_all(["h1", "h2", "h3", "h4", "a", "p", "span"], recursive=True):
            text = clean_text(el.get_text(" ", strip=True))
            if looks_like_real_title(text):
                title_text = text
                break

        if not title_text:
            # Fallback: split lines and find first good non-date text
            parts = [clean_text(x) for x in re.split(r"[\n\r]+", container.get_text("\n", strip=True))]
            for part in parts:
                if looks_like_real_title(part):
                    title_text = part
                    break

        key = f"{date_text} | {title_text or ''}".strip()
        items.append({
            "date": date_text,
            "title": title_text or "",
            "key": key
        })

    # Deduplicate
    seen = set()
    filtered = []

    for item in items:
        key = item["key"]
        if not key or key in seen:
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

    if new_items:
        lines = []
        for item in new_items:
            if item["title"]:
                lines.append(f"• {item['date']} — {item['title']}")
            else:
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
    print(json.dumps({"items": current_items}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
