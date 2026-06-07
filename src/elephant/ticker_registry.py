"""
Shared ticker registry: per-ticker metadata backed by tickers.cache.json.

Cache structure:
{
  "8105.T": {
    "last_seen": "2026-06-06",
    "last_scraped_at": "2026-06-06T10:30:00",
    "speed_history": [
      {"date": "2026-06-06", "comments_per_hour": 12.5},
      {"date": "2026-06-05", "comments_per_hour": 8.2}
    ]
  }
}

Backward compatible: flat {"ticker": "date_str"} entries are migrated on load.
"""

import json
from datetime import datetime
from pathlib import Path


def normalize_ticker(ticker: str) -> str:
    """Add .T suffix only for numeric Tokyo Stock Exchange codes (e.g. '8105' → '8105.T').
    Alphabetic tickers (AMZN, VST) are left unchanged."""
    if "." in ticker:
        return ticker  # already has exchange suffix
    if ticker.isdigit():
        return f"{ticker}.T"
    return ticker


def _cache_path(tickers_file: str) -> Path:
    return Path(tickers_file).with_suffix(".cache.json")


def load_cache(tickers_file: str) -> dict:
    path = _cache_path(tickers_file)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return {}
    return _migrate(raw)


def _migrate(raw: dict) -> dict:
    """Convert flat {ticker: date_str} entries to rich format."""
    result = {}
    for ticker, value in raw.items():
        if isinstance(value, str):
            result[ticker] = {"last_seen": value, "speed_history": []}
        else:
            result[ticker] = value
    return result


def save_cache(tickers_file: str, cache: dict) -> None:
    _cache_path(tickers_file).write_text(json.dumps(cache, indent=2))


def update_speed(tickers_file: str, ticker: str, comment_count: int, scraped_at: datetime) -> None:
    cache = load_cache(tickers_file)
    entry = cache.get(ticker) or {"last_seen": scraped_at.date().isoformat(), "speed_history": []}

    today_str = scraped_at.date().isoformat()

    last_scraped_at_str = entry.get("last_scraped_at")
    if last_scraped_at_str:
        last_scraped_at = datetime.fromisoformat(last_scraped_at_str)
        if last_scraped_at.date() == scraped_at.date():
            hours = max(0.5, (scraped_at - last_scraped_at).total_seconds() / 3600)
        else:
            hours = max(0.5, scraped_at.hour + scraped_at.minute / 60)
    else:
        hours = max(0.5, scraped_at.hour + scraped_at.minute / 60)

    speed = round(comment_count / hours, 2)

    history = entry.get("speed_history", [])
    today_entry = next((h for h in history if h["date"] == today_str), None)
    if today_entry:
        today_entry["comments_per_hour"] = speed
    else:
        history.append({"date": today_str, "comments_per_hour": speed})

    entry["speed_history"] = sorted(history, key=lambda x: x["date"], reverse=True)
    entry["last_scraped_at"] = scraped_at.isoformat()

    cache[ticker] = entry
    save_cache(tickers_file, cache)


def get_speed_history(tickers_file: str, ticker: str) -> list:
    cache = load_cache(tickers_file)
    return cache.get(ticker, {}).get("speed_history", [])
