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

VALID_DECISIONS = {"pass", "watch", "river_candidate", "needs_manual_research"}


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
    snapshot: dict = None,
) -> dict:
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {VALID_DECISIONS}")

    data = _load()
    today = date.today().isoformat()
    existing = data.get(ticker, {})

    suppress_until = None
    pass_count = 1
    decision_history = existing.get("decision_history", [])

    if decision == "pass":
        from datetime import timedelta
        # escalating suppression by pass count
        prior_count = existing.get("pass_count", 0) if existing.get("decision") == "pass" else 0
        pass_count = prior_count + 1
        suppress_days_actual = 28 if pass_count == 1 else (42 if pass_count == 2 else 84)
        suppress_until = (date.today() + timedelta(days=suppress_days_actual)).isoformat()
        # record prior state in history before overwriting
        if existing:
            decision_history = decision_history + [{
                "decision": existing.get("decision"),
                "reason": existing.get("reason", ""),
                "date": existing.get("date", ""),
            }]
    else:
        pass_count = existing.get("pass_count", 1) if existing.get("decision") == "pass" else 1

    entry = {
        "ticker": ticker,
        "decision": decision,
        "reason": reason,
        "date": today,
        "suppress_until": suppress_until,
        "what_would_change": what_would_change,
        "snapshot": snapshot or {},
        "pass_count": pass_count,
        "decision_history": decision_history,
    }

    if decision == "needs_manual_research":
        from datetime import timedelta
        entry["manual_research_due"] = (date.today() + timedelta(days=7)).isoformat()

    data[ticker] = entry
    _save(data)
    return entry


def get(ticker: str) -> Optional[dict]:
    entry = _load().get(ticker)
    if entry and entry.get("decision") == "pass" and "pass_count" not in entry:
        entry["pass_count"] = 1
    return entry


def is_suppressed(ticker: str) -> bool:
    entry = get(ticker)
    if not entry or entry.get("decision") != "pass":
        return False
    suppress_until = entry.get("suppress_until")
    if not suppress_until:
        return False
    return date.today().isoformat() < suppress_until


def check_reset(ticker: str, d4_score: float, best_tier: int) -> bool:
    """Returns True if suppression was cleared due to a qualifying catalyst."""
    entry = get(ticker)
    if not entry or entry.get("decision") != "pass":
        return False
    if not is_suppressed(ticker):
        return False
    pass_count = entry.get("pass_count", 1)
    if best_tier >= 5:
        return False
    reset = False
    if pass_count == 1 and d4_score > 10 and best_tier <= 4:
        reset = True
    elif pass_count == 2 and d4_score > 12 and best_tier <= 3:
        reset = True
    elif pass_count >= 3 and d4_score > 15 and best_tier <= 2:
        reset = True
    if reset:
        data = _load()
        if ticker in data:
            data[ticker]["suppress_until"] = None
            data[ticker]["reset_date"] = date.today().isoformat()
            data[ticker]["reset_by"] = f"d4={d4_score:.1f} tier={best_tier}"
            _save(data)
    return reset


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
