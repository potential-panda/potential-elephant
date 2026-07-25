from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from elephant.config import DATA_DIR, ATLAS_PATH
from elephant.atlas.atlas import Atlas
from elephant.theme.io import load_value_chain_suggestions, load_ticker_theme_scores
from elephant.ticker_registry import is_jp_ticker, normalize_ticker


@dataclass
class ThemeApplyResult:
    evaluated: int
    applied: int
    removed: int
    skipped: int
    dry_run: bool
    changes: list[dict]

    def to_dict(self) -> dict:
        return {
            "evaluated": self.evaluated,
            "applied": self.applied,
            "removed": self.removed,
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


def _eligible_rows(
    df: pd.DataFrame,
    min_score: float,
    min_us_score: float | None,
    suggestion_id: str | None,
) -> pd.DataFrame:
    if df.empty:
        return df
    rows = df.copy()
    if suggestion_id:
        rows = rows[rows["id"].astype(str).eq(str(suggestion_id))]
    else:
        scores = rows["score"].astype(float)
        market = rows.get("market", "").astype(str) if "market" in rows.columns else ""
        if min_us_score is None:
            rows = rows[scores >= float(min_score)]
        else:
            rows = rows[
                ((market == "US") & (scores >= float(min_us_score)))
                | ((market != "US") & (scores >= float(min_score)))
            ]
        if "status" in rows.columns:
            rows = rows[rows["status"].astype(str).ne("existing")]
    return rows.sort_values(["score", "evidence_count"], ascending=[False, False])


def _score_by_ticker_value_chain(scores: pd.DataFrame) -> dict[tuple[str, str], float]:
    if scores.empty:
        return {}
    result: dict[tuple[str, str], float] = {}
    for _, row in scores.iterrows():
        ticker = normalize_ticker(str(row.get("ticker", "")).strip().upper())
        value_chain_id = str(row.get("value_chain_id", "")).strip()
        if not ticker or not value_chain_id:
            continue
        score = float(row.get("score") or 0.0)
        key = (ticker, value_chain_id)
        result[key] = max(result.get(key, 0.0), score)
    return result


def _removable_theme_company(company) -> bool:
    if company.source != "theme_discovery":
        return False
    if company.last_human_decision or company.last_human_decision_date:
        return False
    return True


def apply_value_chain_suggestions(
    *,
    data_dir: str = DATA_DIR,
    atlas_path: str = ATLAS_PATH,
    min_score: float = 30.0,
    min_us_score: float | None = None,
    remove_min_score: float = 28.0,
    remove_min_us_score: float | None = None,
    remove_low_score: bool = True,
    suggestion_id: str | None = None,
    dry_run: bool = True,
) -> ThemeApplyResult:
    suggestions = load_value_chain_suggestions(data_dir)
    rows = _eligible_rows(suggestions, min_score, min_us_score, suggestion_id)
    atlas = Atlas(atlas_path)
    changes = []
    applied = 0
    removed = 0
    skipped = 0

    if remove_low_score and not suggestion_id:
        scores = load_ticker_theme_scores(data_dir)
        if not scores.empty:
            scores_by_key = _score_by_ticker_value_chain(scores)
            removals = []
            for value_chain in atlas.list_value_chains():
                for company in value_chain.companies:
                    if not _removable_theme_company(company):
                        continue
                    current_score = scores_by_key.get((company.ticker, value_chain.id), 0.0)
                    threshold = (
                        float(remove_min_us_score)
                        if remove_min_us_score is not None and not is_jp_ticker(company.ticker)
                        else float(remove_min_score)
                    )
                    if current_score >= threshold:
                        continue
                    removals.append((value_chain.id, company.ticker, current_score, threshold))

            for value_chain_id, ticker, current_score, threshold in sorted(removals, key=lambda item: (item[0], item[1])):
                change = {
                    "action": "remove_company",
                    "ticker": ticker,
                    "value_chain_id": value_chain_id,
                    "score": current_score,
                    "reason": f"theme score below remove threshold {threshold}",
                }
                changes.append(change)
                if dry_run:
                    continue
                if atlas.remove_company(value_chain_id, ticker):
                    removed += 1
                else:
                    skipped += 1

    for _, row in rows.iterrows():
        ticker = normalize_ticker(str(row.get("ticker", "")).strip().upper())
        value_chain_id = str(row.get("value_chain_id", "")).strip()
        stage = str(row.get("stage", "")).strip()
        if not ticker or not value_chain_id or not stage:
            skipped += 1
            changes.append({"action": "skip", "ticker": ticker, "reason": "missing ticker, value_chain_id, or stage"})
            continue
        value_chain = atlas.get_value_chain(value_chain_id)
        if not value_chain:
            skipped += 1
            changes.append({"action": "skip", "ticker": ticker, "value_chain_id": value_chain_id, "reason": "value_chain not found"})
            continue
        existing = any(company.ticker == ticker for company in value_chain.companies)
        if existing:
            skipped += 1
            changes.append({"action": "skip", "ticker": ticker, "value_chain_id": value_chain_id, "reason": "already in value_chain"})
            continue

        suggestion_ref = f"value_chain_suggestion:{row.get('id', '')}"
        change = {
            "action": "add_company",
            "ticker": ticker,
            "value_chain_id": value_chain_id,
            "stage": stage,
            "score": float(row.get("score") or 0),
            "confidence": str(row.get("confidence") or "medium"),
            "peer_group": str(row.get("peer_group") or row.get("theme_id") or ""),
            "evidence_refs": [suggestion_ref],
        }
        changes.append(change)
        if dry_run:
            continue

        company = atlas.add_company(
            value_chain_id=value_chain_id,
            ticker=ticker,
            stage=stage,
            market=str(row.get("market") or "US"),
            name=str(row.get("name") or ""),
            role=str(row.get("reason") or ""),
            source="theme_discovery",
            peer_group=change["peer_group"],
            causal_edge=f"theme evidence -> {row.get('theme_name') or row.get('theme_id')}",
            competitor_tickers=[str(item) for item in _as_list(row.get("competitor_tickers"))],
            leader_tickers=[str(item) for item in _as_list(row.get("leader_tickers"))],
        )
        atlas.update_company(
            value_chain_id,
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
        removed=removed,
        skipped=skipped,
        dry_run=dry_run,
        changes=changes,
    )
