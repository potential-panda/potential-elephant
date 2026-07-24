from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from elephant.config import DATA_DIR, TREE_PATH
from elephant.river.tree import RiverTree
from elephant.theme.catalog import get_theme_definition
from elephant.theme.io import (
    clear_dataset_partition,
    load_etf_holdings,
    load_theme_members,
    row_id,
    save_theme_definitions,
    save_theme_sources,
    write_dataset,
)
from elephant.ticker_registry import is_jp_ticker, normalize_ticker


@dataclass
class ThemeBuildResult:
    score_rows: int
    suggestion_rows: int
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "score_rows": self.score_rows,
            "suggestion_rows": self.suggestion_rows,
            "generated_at": self.generated_at,
        }


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value == "":
            return default
        result = float(value)
    except Exception:
        return default
    return result if math.isfinite(result) else default


def _recency_factor(value) -> float:
    if not value:
        return 1.0
    try:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return 1.0
        days = max(0.0, (pd.Timestamp.now(tz=None) - dt.tz_localize(None)).total_seconds() / 86400)
        return max(0.25, min(1.0, 1.0 - days / 365.0))
    except Exception:
        return 1.0


def _holding_factor(value) -> float:
    weight = _safe_float(value, default=0.0)
    if weight <= 0:
        return 0.35
    if weight <= 1:
        weight *= 100.0
    return 0.35 + min(weight, 10.0) / 10.0


def _rank_factor(value) -> float:
    rank = _safe_float(value, default=0.0)
    if rank <= 0:
        return 1.0
    return max(0.25, 1.0 / (1.0 + rank / 20.0))


def _normalize_score(raw_score: float) -> float:
    return round(100.0 * (1.0 - math.exp(-max(0.0, raw_score) / 2.0)), 2)


def _assign_theme_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["assigned"] = False
    for theme_id, group in df.groupby("theme_id"):
        theme_scores = group["score"].astype(float)
        if theme_scores.empty:
            continue
        relative_threshold = max(28.0, float(theme_scores.quantile(0.85)))
        assigned = (
            (theme_scores >= 50.0)
            | ((group["evidence_count"].astype(float) >= 2) & (theme_scores >= 30.0))
            | ((theme_scores >= relative_threshold) & (theme_scores >= 28.0))
        )
        df.loc[group.index, "assigned"] = assigned
    return df


def _existing_tree_tickers(tree_path: str = TREE_PATH) -> set[str]:
    tree = RiverTree(tree_path)
    return {node.ticker for river in tree.list_rivers() for node in river.nodes}


def build_ticker_theme_scores(data_dir: str = DATA_DIR) -> pd.DataFrame:
    evidence: dict[tuple[str, str], dict] = {}

    theme_members = load_theme_members(data_dir)
    if not theme_members.empty:
        for _, row in theme_members.iterrows():
            theme_id = str(row.get("theme_id", "")).strip()
            ticker = normalize_ticker(str(row.get("ticker", "")).strip().upper())
            if not theme_id or not ticker:
                continue
            definition = get_theme_definition(theme_id)
            if not definition and theme_id.startswith("raw_"):
                # Keep raw source themes available for audit, but do not turn
                # unconsolidated theme names into final ticker assignments.
                continue
            purity = _safe_float(row.get("theme_purity"), default=definition.theme_purity if definition else 0.75)
            source = str(row.get("source") or "theme_member")
            source_quality = 0.75 if source.startswith("minkabu") else 0.65
            raw = source_quality * purity * _rank_factor(row.get("raw_rank")) * _safe_float(row.get("source_weight"), 1.0)
            item = evidence.setdefault((ticker, theme_id), {"raw_score": 0.0, "evidence": []})
            item["raw_score"] += raw
            item["evidence"].append({
                "kind": "theme_member",
                "source": source,
                "source_url": row.get("source_url") or "",
                "score": round(raw, 4),
            })

    etf_holdings = load_etf_holdings(data_dir)
    if not etf_holdings.empty:
        for _, row in etf_holdings.iterrows():
            theme_id = str(row.get("theme_id", "")).strip()
            ticker = normalize_ticker(str(row.get("ticker", "")).strip().upper())
            if not theme_id or not ticker:
                continue
            definition = get_theme_definition(theme_id)
            purity = _safe_float(row.get("theme_purity"), default=definition.theme_purity if definition else 0.7)
            raw = (
                purity
                * _safe_float(row.get("issuer_quality"), 1.0)
                * _recency_factor(row.get("as_of"))
                * _holding_factor(row.get("holding_weight"))
            )
            item = evidence.setdefault((ticker, theme_id), {"raw_score": 0.0, "evidence": []})
            item["raw_score"] += raw
            item["evidence"].append({
                "kind": "etf_holding",
                "etf": row.get("etf") or "",
                "issuer": row.get("issuer") or "",
                "holding_weight": row.get("holding_weight") or "",
                "source_url": row.get("source_url") or "",
                "score": round(raw, 4),
            })

    generated_at = datetime.now().isoformat(timespec="seconds")
    rows = []
    for (ticker, theme_id), item in evidence.items():
        definition = get_theme_definition(theme_id)
        raw_score = item["raw_score"]
        rows.append({
            "id": row_id("ticker_theme_score", ticker, theme_id, generated_at),
            "ticker": ticker,
            "theme_id": theme_id,
            "theme_name": definition.name if definition else theme_id,
            "river_id": definition.river_id if definition else "",
            "layer_hint": definition.layer_hint if definition else "",
            "raw_score": round(raw_score, 4),
            "score": _normalize_score(raw_score),
            "assigned": _normalize_score(raw_score) >= 50.0,
            "evidence_count": len(item["evidence"]),
            "evidence_json": json.dumps(item["evidence"], ensure_ascii=False),
            "generated_at": generated_at,
        })
    if not rows:
        return pd.DataFrame()
    return _assign_theme_rows(pd.DataFrame(rows)).sort_values(["score", "evidence_count"], ascending=[False, False])


def _build_similarity(score_df: pd.DataFrame) -> dict[str, list[dict]]:
    if score_df.empty:
        return {}
    pivot = score_df.pivot_table(index="ticker", columns="theme_id", values="raw_score", aggfunc="sum", fill_value=0.0)
    norms = {ticker: math.sqrt(sum(v * v for v in pivot.loc[ticker].values)) for ticker in pivot.index}
    result: dict[str, list[dict]] = {}
    for ticker in pivot.index:
        peers = []
        a = pivot.loc[ticker].values
        for other in pivot.index:
            if other == ticker:
                continue
            denom = norms[ticker] * norms[other]
            if denom <= 0:
                continue
            sim = float(sum(a * pivot.loc[other].values) / denom)
            if sim >= 0.35:
                peers.append({"ticker": other, "similarity": round(sim, 3)})
        result[ticker] = sorted(peers, key=lambda row: row["similarity"], reverse=True)[:8]
    return result


def build_river_suggestions(score_df: pd.DataFrame, tree_path: str = TREE_PATH) -> pd.DataFrame:
    if score_df.empty:
        return pd.DataFrame()
    known = _existing_tree_tickers(tree_path)
    similarity = _build_similarity(score_df)
    grouped = defaultdict(list)
    for _, row in score_df.iterrows():
        grouped[row["ticker"]].append(row)

    generated_at = datetime.now().isoformat(timespec="seconds")
    suggestions = []
    for ticker, rows in grouped.items():
        rows = sorted(rows, key=lambda r: (r["score"], r["evidence_count"]), reverse=True)
        best = rows[0]
        if not best.get("river_id") or not bool(best.get("assigned")):
            continue
        confidence = "high" if best["score"] >= 30 else "medium" if best["score"] >= 28 else "low"
        peers = similarity.get(ticker, [])
        suggestions.append({
            "id": row_id("river_suggestion", ticker, best["theme_id"], generated_at),
            "ticker": ticker,
            "market": "JP" if is_jp_ticker(ticker) else "US",
            "river_id": best["river_id"],
            "layer": best["layer_hint"] or "middle",
            "theme_id": best["theme_id"],
            "theme_name": best["theme_name"],
            "score": best["score"],
            "confidence": confidence,
            "status": "existing" if ticker in known else "proposed",
            "peer_group": best["theme_id"],
            "competitor_tickers": [p["ticker"] for p in peers[:5]],
            "leader_tickers": [p["ticker"] for p in peers[:3]],
            "evidence_count": int(sum(_safe_float(r.get("evidence_count")) for r in rows)),
            "evidence_json": best["evidence_json"],
            "reason": (
                f"{ticker} maps to {best['theme_name']} with score {best['score']} "
                f"from {int(best['evidence_count'])} evidence rows."
            ),
            "generated_at": generated_at,
        })
    if not suggestions:
        return pd.DataFrame()
    return pd.DataFrame(suggestions).sort_values(["status", "score"], ascending=[False, False])


def build_theme_river_system(data_dir: str = DATA_DIR, tree_path: str = TREE_PATH, save: bool = False) -> ThemeBuildResult:
    scores = build_ticker_theme_scores(data_dir)
    suggestions = build_river_suggestions(scores, tree_path)
    if save:
        save_theme_definitions(data_dir)
        save_theme_sources(data_dir)
        if not scores.empty:
            write_dataset("ticker_theme_scores", scores.to_dict("records"), data_dir, replace=True)
        else:
            clear_dataset_partition("ticker_theme_scores", data_dir)
        if not suggestions.empty:
            write_dataset("river_suggestions", suggestions.to_dict("records"), data_dir, replace=True)
        else:
            clear_dataset_partition("river_suggestions", data_dir)
    return ThemeBuildResult(
        score_rows=0 if scores.empty else len(scores),
        suggestion_rows=0 if suggestions.empty else len(suggestions),
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )
