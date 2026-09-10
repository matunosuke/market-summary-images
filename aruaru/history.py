"""投稿済みネタの履歴。同じ題材の繰り返しを避けるために使う。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .tweet_text import Aruaru

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "history.json"

# 直近何件のタイトルをモデルに渡すか
RECENT_WINDOW = 30


def load(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def recent_titles(entries: list[dict], limit: int = RECENT_WINDOW) -> list[str]:
    titles = [entry.get("title", "") for entry in entries if entry.get("title")]
    return titles[-limit:]


def append(
    aruaru: Aruaru,
    tweet_id: str | None,
    posted_on: date,
    path: Path = DEFAULT_PATH,
) -> None:
    entries = load(path)
    entries.append(
        {
            "date": posted_on.isoformat(),
            "title": aruaru.title,
            "text": aruaru.render(),
            "tweet_id": tweet_id,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")
