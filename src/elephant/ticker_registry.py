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


def is_jp_ticker(ticker: str) -> bool:
    """Returns True for Tokyo Stock Exchange tickers (e.g. 8105.T, 6920.T)."""
    return ticker.endswith(".T")


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


def mark_yahoo_jp_bbs(tickers_file: str, ticker: str, has_bbs: bool) -> None:
    """Persist whether a ticker has a reachable Yahoo JP BBS page."""
    cache = load_cache(tickers_file)
    entry = cache.get(ticker) or {}
    if not isinstance(entry, dict):
        entry = {}
    entry["has_yahoo_jp_bbs"] = has_bbs
    cache[ticker] = entry
    save_cache(tickers_file, cache)
    _sync_us_ticker_entry(tickers_file, ticker, entry)


def get_yahoo_jp_bbs_status(cache: dict, ticker: str) -> bool | None:
    """Return True/False/None (None = not yet probed)."""
    entry = cache.get(ticker)
    if not isinstance(entry, dict):
        return None
    val = entry.get("has_yahoo_jp_bbs")
    return val  # True / False / None


def mark_minkabu_us(tickers_file: str, ticker: str, has_page: bool) -> None:
    """Persist whether a US ticker has a reachable us.minkabu.jp page."""
    cache = load_cache(tickers_file)
    entry = cache.get(ticker) or {}
    if not isinstance(entry, dict):
        entry = {}
    entry["has_minkabu_us"] = has_page
    cache[ticker] = entry
    save_cache(tickers_file, cache)
    _sync_us_ticker_entry(tickers_file, ticker, entry)


def get_minkabu_us_status(cache: dict, ticker: str) -> bool | None:
    """Return True/False/None (None = not yet probed)."""
    entry = cache.get(ticker)
    if not isinstance(entry, dict):
        return None
    return entry.get("has_minkabu_us")


def _us_tickers_path(tickers_file: str) -> Path:
    return Path(tickers_file).parent / "tickers-us.txt"


_FLAG_TO_STR = {True: "true", False: "false", None: "unknown"}
_STR_TO_FLAG = {"true": True, "false": False, "unknown": None}


def load_us_tickers(tickers_file: str) -> dict[str, dict]:
    """Confirmed US tickers: {ticker: {"bbs": bool|None, "minkabu": bool|None}}.

    A ticker appears here once either Yahoo JP BBS or Minkabu confirms a
    reachable page for it. The other flag may still be `None` (not yet
    probed) at that point. This is the explicit, human-readable companion to
    tickers.txt (JP BBS rank order) that the daily scheduler reads to decide
    which US tickers get full-depth scraping.
    """
    path = _us_tickers_path(tickers_file)
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        ticker = parts[0]
        flags = {"bbs": None, "minkabu": None}
        for part in parts[1:]:
            key, _, val = part.partition("=")
            if key in flags:
                flags[key] = _STR_TO_FLAG.get(val.lower())
        result[ticker] = flags
    return result


def _save_us_tickers(tickers_file: str, entries: dict[str, dict]) -> None:
    path = _us_tickers_path(tickers_file)
    lines = [
        f"{ticker} bbs={_FLAG_TO_STR[v.get('bbs')]} minkabu={_FLAG_TO_STR[v.get('minkabu')]}"
        for ticker, v in sorted(entries.items())
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def _sync_us_ticker_entry(tickers_file: str, ticker: str, entry: dict) -> None:
    """Add/refresh ticker in tickers-us.txt once it has a confirmed BBS or Minkabu page."""
    if is_jp_ticker(ticker):
        return
    bbs_val = entry.get("has_yahoo_jp_bbs")
    minkabu_val = entry.get("has_minkabu_us")
    if bbs_val is not True and minkabu_val is not True:
        return  # neither source confirmed yet; don't register
    entries = load_us_tickers(tickers_file)
    entries[ticker] = {"bbs": bbs_val, "minkabu": minkabu_val}
    _save_us_tickers(tickers_file, entries)
