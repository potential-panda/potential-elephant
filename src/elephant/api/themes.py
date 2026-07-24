from __future__ import annotations

from elephant.config import DATA_DIR
from elephant.theme.catalog import list_theme_sources
from elephant.theme.apply import apply_river_suggestions
from elephant.theme.builder import build_theme_river_system
from elephant.theme.harvest import harvest_theme_sources
from elephant.theme.io import load_river_suggestions, load_theme_source_themes, load_ticker_theme_scores


def _records(df, limit: int = 100) -> list[dict]:
    if df.empty:
        return []
    return df.head(limit).fillna("").to_dict("records")


def get_theme_scores(limit: int = 100) -> dict:
    df = load_ticker_theme_scores(DATA_DIR)
    if not df.empty and "score" in df.columns:
        df = df.sort_values(["score", "evidence_count"], ascending=[False, False])
    return {"items": _records(df, limit), "total": 0 if df.empty else len(df)}


def get_source_themes(limit: int = 100) -> dict:
    df = load_theme_source_themes(DATA_DIR)
    if not df.empty and "rank" in df.columns:
        df = df.sort_values(["source_id", "rank"], ascending=[True, True])
    return {"items": _records(df, limit), "total": 0 if df.empty else len(df)}


def get_river_suggestions(limit: int = 100, include_existing: bool = True) -> dict:
    df = load_river_suggestions(DATA_DIR)
    if not df.empty:
        if not include_existing and "status" in df.columns:
            df = df[df["status"] != "existing"]
        if "score" in df.columns:
            df = df.sort_values(["score"], ascending=False)
    return {"items": _records(df, limit), "total": 0 if df.empty else len(df)}


def build_themes(save: bool = True) -> dict:
    return build_theme_river_system(DATA_DIR, save=save).to_dict()


def get_theme_sources() -> dict:
    items = [source.to_dict() for source in list_theme_sources(enabled_only=False)]
    return {"items": items, "total": len(items)}


def harvest_sources(source_id: str | None = None) -> dict:
    items = harvest_theme_sources(source_id=source_id, data_dir=DATA_DIR)
    return {"items": items, "total": len(items)}


def apply_suggestions(min_score: float = 30.0, suggestion_id: str | None = None, dry_run: bool = True) -> dict:
    return apply_river_suggestions(
        data_dir=DATA_DIR,
        min_score=min_score,
        suggestion_id=suggestion_id,
        dry_run=dry_run,
    ).to_dict()
