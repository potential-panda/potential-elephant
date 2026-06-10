"""
Decision log — persists pass/watch/river_candidate decisions per ticker.

Stored at $DATA_DIR/decisions.json as a dict keyed by ticker.
CandidateMetrics uses this to suppress previously-passed tickers.
"""

import json
import os
from datetime import datetime, date
from typing import Optional

from elephant.config import DECISIONS_FILE

VALID_DECISIONS = {"pass", "watch", "river_candidate"}


def _load() -> dict:
    if not os.path.exists(DECISIONS_FILE):
        return {}
    try:
        return json.loads(open(DECISIONS_FILE, encoding="utf-8").read())
    except Exception:
        return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(DECISIONS_FILE), exist_ok=True)
    with open(DECISIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def record(
    ticker: str,
    decision: str,
    reason: str = "",
    suppress_days: int = 30,
    what_would_change: str = "",
) -> dict:
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {VALID_DECISIONS}")

    data = _load()
    today = date.today().isoformat()
    suppress_until = None
    if decision == "pass":
        from datetime import timedelta
        suppress_until = (date.today() + timedelta(days=suppress_days)).isoformat()

    entry = {
        "ticker": ticker,
        "decision": decision,
        "reason": reason,
        "date": today,
        "suppress_until": suppress_until,
        "what_would_change": what_would_change,
    }
    data[ticker] = entry
    _save(data)
    return entry


def get(ticker: str) -> Optional[dict]:
    return _load().get(ticker)


def is_suppressed(ticker: str) -> bool:
    entry = get(ticker)
    if not entry or entry.get("decision") != "pass":
        return False
    suppress_until = entry.get("suppress_until")
    if not suppress_until:
        return False
    return date.today().isoformat() < suppress_until


def list_all() -> list[dict]:
    data = _load()
    return sorted(data.values(), key=lambda e: e.get("date", ""), reverse=True)


def remove(ticker: str) -> bool:
    data = _load()
    if ticker in data:
        del data[ticker]
        _save(data)
        return True
    return False
