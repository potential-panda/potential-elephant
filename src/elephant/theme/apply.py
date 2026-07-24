from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from elephant.config import DATA_DIR, TREE_PATH
from elephant.river.tree import RiverTree
from elephant.theme.io import load_river_suggestions
from elephant.ticker_registry import normalize_ticker


@dataclass
class ThemeApplyResult:
    evaluated: int
    applied: int
    skipped: int
    dry_run: bool
    changes: list[dict]

    def to_dict(self) -> dict:
        return {
            "evaluated": self.evaluated,
            "applied": self.applied,
            "skipped": self.skipped,
            "dry_run": self.dry_run,
            "changes": self.changes,
        }


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass
    if not value or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            loaded = json.loads(text)
            return loaded if isinstance(loaded, list) else [loaded]
        except Exception:
            return [text]
    return [value]


def _eligible_rows(df: pd.DataFrame, min_score: float, suggestion_id: str | None) -> pd.DataFrame:
    if df.empty:
        return df
    rows = df.copy()
    if suggestion_id:
        rows = rows[rows["id"].astype(str).eq(str(suggestion_id))]
    else:
        rows = rows[rows["score"].astype(float) >= float(min_score)]
        if "status" in rows.columns:
            rows = rows[rows["status"].astype(str).ne("existing")]
    return rows.sort_values(["score", "evidence_count"], ascending=[False, False])


def apply_river_suggestions(
    *,
    data_dir: str = DATA_DIR,
    tree_path: str = TREE_PATH,
    min_score: float = 30.0,
    suggestion_id: str | None = None,
    dry_run: bool = True,
) -> ThemeApplyResult:
    suggestions = load_river_suggestions(data_dir)
    rows = _eligible_rows(suggestions, min_score, suggestion_id)
    tree = RiverTree(tree_path)
    changes = []
    applied = 0
    skipped = 0

    for _, row in rows.iterrows():
        ticker = normalize_ticker(str(row.get("ticker", "")).strip().upper())
        river_id = str(row.get("river_id", "")).strip()
        layer = str(row.get("layer", "")).strip()
        if not ticker or not river_id or not layer:
            skipped += 1
            changes.append({"action": "skip", "ticker": ticker, "reason": "missing ticker, river_id, or layer"})
            continue
        river = tree.get_river(river_id)
        if not river:
            skipped += 1
            changes.append({"action": "skip", "ticker": ticker, "river_id": river_id, "reason": "river not found"})
            continue
        existing = any(node.ticker == ticker for node in river.nodes)
        if existing:
            skipped += 1
            changes.append({"action": "skip", "ticker": ticker, "river_id": river_id, "reason": "already in river"})
            continue

        suggestion_ref = f"river_suggestion:{row.get('id', '')}"
        change = {
            "action": "add_node",
            "ticker": ticker,
            "river_id": river_id,
            "layer": layer,
            "score": float(row.get("score") or 0),
            "confidence": str(row.get("confidence") or "medium"),
            "peer_group": str(row.get("peer_group") or row.get("theme_id") or ""),
            "evidence_refs": [suggestion_ref],
        }
        changes.append(change)
        if dry_run:
            continue

        node = tree.add_node(
            river_id=river_id,
            ticker=ticker,
            layer=layer,
            market=str(row.get("market") or "US"),
            name=str(row.get("name") or ""),
            role=str(row.get("reason") or ""),
            source="theme_discovery",
            peer_group=change["peer_group"],
            causal_edge=f"theme evidence -> {row.get('theme_name') or row.get('theme_id')}",
            competitor_tickers=[str(item) for item in _as_list(row.get("competitor_tickers"))],
            leader_tickers=[str(item) for item in _as_list(row.get("leader_tickers"))],
        )
        tree.update_node(
            river_id,
            ticker,
            status="proposed",
            confidence=change["confidence"],
            thesis=str(row.get("reason") or ""),
            last_reviewed=datetime.now().strftime("%Y-%m-%d"),
            evidence_refs=change["evidence_refs"],
            what_would_change_our_mind="Relationship score weakens below promotion threshold or source evidence is rejected.",
        )
        applied += 1

    return ThemeApplyResult(
        evaluated=len(rows),
        applied=applied,
        skipped=skipped,
        dry_run=dry_run,
        changes=changes,
    )
