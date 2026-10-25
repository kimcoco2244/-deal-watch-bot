#!/usr/bin/env python3
"""Public hot-deal board watcher. No login, bypass or price certainty claims."""
import calendar
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import feedparser
import requests
from bs4 import BeautifulSoup

STATE = Path(".state/seen.json")
UA = {"User-Agent": "DealWatchBot/1.0 (+personal price alerts; public pages only)"}
SOURCES = [
    ("뽐뿌", "rss", "https://www.ppomppu.co.kr/rss.php?id=ppomppu"),
    ("해외뽐뿌", "rss", "https://www.ppomppu.co.kr/rss.php?id=ppomppu4"),
    ("아카라이브 핫딜", "html", "https://arca.live/b/hotdeal"),
    ("루리웹 핫딜", "html", "https://bbs.ruliweb.com/market/board/1020"),
]
ERROR_TERMS = [
    "가격오류", "가격 오류", "가격실수", "가격 실수", "가격오타", "가격 오타",
    "오기가격", "오기재", "가격버그", "가격 버그", "오류딜",
    "오류가", "오표기", "잘못된 가격", "잘못 올라온", "가격 잘못",
    "쿠폰 오류", "쿠폰오류", "0원딜", "0원 딜",
]
DEAL_TERMS = [
    "역대가", "역대급", "초특가", "대란", "반값", "떨이",
    "득템", "가격파괴", "가격 미쳤", "가격미쳤", "80% 할인", "90% 할인",
    "80%할인", "90%할인", "초저가", "핫딜", "파격가",
]
EXCLUDE_TERMS = ["[종료]", "(종료)", "[품절]", "(품절)", "[마감]", "(마감)"]
RECENT_MINUTES = int(os.getenv("RECENT_MINUTES", "45"))
TIMEOUT = 13


def utcnow():
    return datetime.now(timezone.utc)


def text_only(raw):
    return BeautifulSoup(html.unescape(str(raw or "")), "html.parser").get_text(" ", strip=True)


def good_link(url):
    try:
        p = urlsplit(url)
        return p.scheme in ("https", "http") and bool(p.netloc)
    except (ValueError, TypeError):
        return False


def classify(title):
    compact = re.sub(r"\s+", " ", title).strip().lower()
    if any(t in compact for t in ERROR_TERMS):
        return "가격 오류 의심"
    if any(t in compact for t in EXCLUDE_TERMS):
        return None
    if any(t in compact for t in DEAL_TERMS):
        return "초특가 제보"
    return None


def fetch_rss(name, url):
    res = requests.get(url, headers=UA, timeout=TIMEOUT)
    res.raise_for_status()
    feed = feedparser.parse(res.content)
    if feed.bozo and not feed.entries:
        raise ValueError("RSS parse error")
    items = []
    for entry in feed.entries[:55]:
        title = text_only(entry.get("title", ""))
        link = entry.get("link", "")
        if not good_link(link) or not title:
            continue
        tm = entry.get("published_parsed") or entry.get("updated_parsed")
        posted = datetime.fromtimestamp(calendar.timegm(tm), timezone.utc) if tm else None
        items.append({"source": name, "title": title, "link": link, "posted": posted})
    return items


def fetch_html(name, url):
    res = requests.get(url, headers={**UA, "User-Agent": "Mozilla/5.0 (compatible; DealWatchBot/1.0)"}, timeout=TIMEOUT)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    items, visited = [], set()
    if "arca.live" in url:
        pattern = re.compile(r"/b/hotdeal/\d+")
    else:
        pattern = re.compile(r"/market/board/1020/read/\d+")
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if not pattern.search(href):
            continue
        link = urljoin(url, href).split("#", 1)[0]
        title = text_only(a.get_text(" ", strip=True))
        if not (8 <= len(title) <= 220) or link in visited or not good_link(link):
            continue
        visited.add(link)
        items.append({"source": name, "title": title, "link": link, "posted": None})
        if len(items) >= 75:
            break
    return items


def item_id(item):
    # Only post URLs/hashes are tracked; never store Telegram secrets.
    return hashlib.sha256(item["link"].encode("utf-8")).hexdigest()[:24]


def load_state():
    if not STATE.exists():
        return {"initialized": False, "seen": {}, "heartbeat_day": ""}
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if not isinstance(state.get("seen"), dict):
            raise ValueError("invalid state")
        return state
    except (json.JSONDecodeError, ValueError):
        raise RuntimeError("State unreadable; refusing to reset and resend historical posts")


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def send_message(token, chat_id, message):
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=TIMEOUT,
    )
    if not resp.ok:
        # Do not print token-bearing HTTP URLs or raw responses in public CI logs.
        if resp.status_code == 401:
            reason = "Telegram token is invalid or has been revoked"
        elif resp.status_code == 400:
            reason = "Telegram chat ID may be invalid; ensure you started the bot"
        elif resp.status_code == 403:
            reason = "Telegram bot is blocked or cannot message this chat"
        else:
            reason = "Telegram server returned an error"
        raise RuntimeError(f"{reason} (HTTP {resp.status_code})")
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError("Telegram returned non-ok response")


def format_message(item, label):
    title = html.escape(item["title"][:180])
    origin = html.escape(item["source"])
    link = html.escape(item["link"], quote=True)
    return (f"<b>[{html.escape(label)}] {title}</b>\n"
            f"게시판: {origin}\n"
            f"원문: <a href=\"{link}\">확인하기</a>\n\n"
            "게시글 제목의 키워드로 감지한 제보입니다. "
            "판매 가격·재고·가격 오류 여부는 직접 확인하세요.")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        missing = ", ".join(key for key, value in (
            ("TELEGRAM_BOT_TOKEN", token),
            ("TELEGRAM_CHAT_ID", chat_id),
        ) if not value)
        print(f"SETUP NEEDED: missing repository Actions secret(s): {missing}")
        return 1
    if os.getenv("SEND_TEST", "false").lower() == "true":
        try:
            send_message(token, chat_id, "특가 감시봇 테스트 성공! GitHub Actions 연결이 정상입니다.")
        except requests.RequestException:
            print("ERROR: Telegram API network request failed.")
            return 1
        except (RuntimeError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 1
        print("Test notification sent.")
        return 0

    state = load_state()
    now = utcnow()
    found, successful, failures = [], 0, 0
    for name, kind, url in SOURCES:
        try:
            items = fetch_rss(name, url) if kind == "rss" else fetch_html(name, url)
            if not items:
                print(f"WARN {name}: no posts parsed; source structure may have changed")
                continue
            successful += 1
            found.extend(items)
            print(f"OK {name}: {len(items)} posts")
        except (requests.RequestException, ValueError) as exc:
            failures += 1
            print(f"WARN {name}: fetch/parse failed: {type(exc).__name__}")
    if not successful:
        print("ERROR: no sources returned usable posts. Check site blocking or parser.")
        return 1

    # Prune at least once a day so the public-repo scheduled workflow stays active.
    today = now.strftime("%Y-%m-%d")
    dirty = state.get("heartbeat_day") != today
    if dirty:
        oldest = now - timedelta(days=30)
        state["seen"] = {
            k: v for k, v in state["seen"].items()
            if isinstance(v, str) and v >= oldest.isoformat()
        }
        state["heartbeat_day"] = today

    if not state.get("initialized", False):
        # Bootstrap: don't bombard the user with posts already present.
        for item in found:
            if classify(item["title"]):
                state["seen"][item_id(item)] = now.isoformat()
        state["initialized"] = True
        save_state(state)
        print("Initialized baseline without sending past deals.")
        return 0

    matches = 0
    errors = 0
    for item in found:
        label = classify(item["title"])
        if label is None:
            continue
        key = item_id(item)
        if key in state["seen"]:
            continue
        posted = item["posted"]
        # RSS dates are reliable enough to avoid late historical alerts.
        if posted and (now - posted > timedelta(minutes=RECENT_MINUTES) or
                       posted - now > timedelta(minutes=5)):
            state["seen"][key] = now.isoformat()
            dirty = True
            continue
        try:
            send_message(token, chat_id, format_message(item, label))
            state["seen"][key] = now.isoformat()
            dirty = True
            matches += 1
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            errors += 1
            print(f"ERROR: Telegram delivery failed: {type(exc).__name__}")
    if dirty:
        save_state(state)
    print(f"Scan finished: {successful} sources OK, {failures} failures, {matches} alerts, {errors} delivery errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
