from datetime import datetime
from pathlib import Path

import pandas as pd

from elephant.analysis.loaders import (
    load_minkabu,
    load_news_for_ticker,
    load_prices,
    load_tdnet_for_ticker,
    load_yjp_comments,
    load_yjp_evaluations,
)
from elephant.analysis.pipeline import load_latest_score
from elephant.api.dive import get_latest as get_dive_latest
from elephant.api.detail import _sort_comments
from elephant.api.prices import get_price_changes
from elephant.config import DATA_DIR
from elephant.source.catalog import list_sources
from elephant.source.registry import SourceRegistry
from elephant.ticker_registry import is_jp_ticker, normalize_ticker


def _jsonable(value):
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "tolist") and not isinstance(value, str):
        try:
            return _jsonable(value.tolist())
        except Exception:
            pass
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def _df_records(df: pd.DataFrame, limit: int = 20, sort_columns: list[str] | None = None, ascending: bool = False) -> list[dict]:
    if df is None or df.empty:
        return []
    frame = df.copy()
    if sort_columns:
        cols = [c for c in sort_columns if c in frame.columns]
        if cols:
            frame = frame.sort_values(cols, ascending=ascending)
    elif "scraped_at" in frame.columns:
        frame["scraped_at"] = pd.to_datetime(frame["scraped_at"], errors="coerce")
        frame = frame.sort_values("scraped_at", ascending=False)
    return _jsonable(frame.head(limit).fillna("").to_dict("records"))


def _load_latest_signals(ticker: str) -> list[dict]:
    canonical = normalize_ticker(ticker)
    root = Path(DATA_DIR) / "dataset=ticker_analysis_signals" / f"ticker={canonical}"
    files = sorted(root.glob("date=*/data.parquet"), reverse=True)
    if not files:
        return []
    try:
        df = pd.read_parquet(files[0])
    except Exception:
        return []
    if df.empty:
        return []
    sort_cols = [c for c in ["weight", "confidence", "analyzed_at"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=[False, False, False][: len(sort_cols)])
    return _df_records(df, limit=50)


def _load_minkabu_latest(ticker: str) -> dict | None:
    df = load_minkabu(ticker)
    if df.empty:
        return None
    if "scraped_at" in df.columns:
        df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
        df = df.sort_values("scraped_at", ascending=False)
    row = df.iloc[0].to_dict()
    result = {}
    for key in ["analysis", "research", "pick", "analyst_consensus"]:
        text = str(row.get(key, "") or "").strip()
        if text:
            result[key] = text
    if not result:
        return None
    result["scraped_at"] = _jsonable(row.get("scraped_at"))
    return result


def _load_news(ticker: str) -> list[dict]:
    df = load_news_for_ticker(ticker, days=14)
    if df.empty:
        return []
    if "published" in df.columns:
        df["published_dt"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
        df = df.sort_values(["published_dt"], ascending=False)
    return _df_records(df, limit=30)


def _load_tdnet(ticker: str) -> list[dict]:
    df = load_tdnet_for_ticker(ticker, days=30)
    if df.empty:
        return []
    sort_cols = [c for c in ["date", "time", "scraped_at"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=[False, False, False][: len(sort_cols)])
    return _df_records(df, limit=30)


def _infer_source_from_loaded_data(ticker: str, source_id: str, rows: list[dict]) -> dict | None:
    if source_id != "fool_quote_news" or not rows:
        return None
    fool_rows = [
        row for row in rows
        if row.get("quote_url") or row.get("source") == "fool_us_quote_news"
    ]
    if not fool_rows:
        return None

    from elephant.source.availability import source_symbol_and_urls

    symbol, fallback_urls = source_symbol_and_urls(source_id, ticker)
    urls = [str(row.get("quote_url")).strip() for row in fool_rows if row.get("quote_url")]
    urls = list(dict.fromkeys(url for url in urls if url))
    harvested_at = None
    scraped_values = [row.get("scraped_at") for row in fool_rows if row.get("scraped_at")]
    if scraped_values:
        try:
            harvested_at = max(pd.to_datetime(scraped_values, errors="coerce")).isoformat()
        except Exception:
            harvested_at = None
    return {
        "ticker": normalize_ticker(ticker),
        "source_id": source_id,
        "status": "available",
        "source_symbol": symbol,
        "urls": urls or fallback_urls,
        "checked_at": harvested_at or "",
        "last_harvested_at": harvested_at,
        "last_row_count": len(fool_rows),
        "availability_inferred_from_dataset": True,
    }


def _load_comments(ticker: str) -> list[dict]:
    df = load_yjp_comments(ticker)
    if df.empty:
        return []
    try:
        df = _sort_comments(df)
    except Exception:
        if "scraped_at" in df.columns:
            df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
            df = df.sort_values("scraped_at", ascending=False)
    return _df_records(df, limit=40)


def _load_evaluations(ticker: str) -> list[dict]:
    df = load_yjp_evaluations(ticker)
    if df.empty:
        return []
    if "scraped_at" in df.columns:
        df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
        df = df.sort_values("scraped_at", ascending=False)
    return _df_records(df, limit=20)


def _load_prices_detail(ticker: str) -> dict:
    price_summary = get_price_changes([ticker]).get(ticker) or {}
    df = load_prices(ticker)
    history = []
    if not df.empty:
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.sort_values("date", ascending=False)
        history = _df_records(df, limit=30)
    return {"summary": _jsonable(price_summary), "history": history}


def get_detail(ticker_raw: str) -> dict:
    ticker = normalize_ticker(ticker_raw.strip())
    market = "JP" if is_jp_ticker(ticker) else "US"
    registry = SourceRegistry()
    source_defs = list_sources(scope="ticker")
    resolved_sources = registry.resolved_sources(ticker)
    news = _load_news(ticker)
    fool_inferred = _infer_source_from_loaded_data(ticker, "fool_quote_news", news)
    if fool_inferred:
        current = resolved_sources.get("fool_quote_news") or {}
        if current.get("status") != "available" or not current.get("urls"):
            resolved_sources["fool_quote_news"] = fool_inferred

    sources = []
    for source_def in source_defs:
        source = resolved_sources.get(source_def.source_id) or {"status": "unknown", "urls": []}
        sources.append(
            {
                "source_id": source_def.source_id,
                "name": source_def.name,
                "description": source_def.description,
                "status": source.get("status", "unknown"),
                "urls": source.get("urls", []),
                "checked_at": source.get("checked_at"),
                "last_harvested_at": source.get("last_harvested_at"),
                "last_row_count": source.get("last_row_count"),
                "last_error": source.get("last_error"),
                "dataset": source_def.dataset,
                "harvester": source_def.harvester,
            }
        )

    score = load_latest_score(ticker)
    signals = _load_latest_signals(ticker)
    analysis = None
    if score or signals:
        analysis = {
            "score": _jsonable(score) if score else None,
            "signals": signals,
        }

    return {
        "ticker": ticker,
        "bare": ticker[:-2] if ticker.endswith(".T") else ticker,
        "market": market,
        "analysis": analysis,
        "price": _load_prices_detail(ticker),
        "sources": sources,
        "dive": get_dive_latest(ticker),
        "comments": _load_comments(ticker),
        "evaluations": _load_evaluations(ticker),
        "minkabu": _load_minkabu_latest(ticker),
        "news": news,
        "tdnet": _load_tdnet(ticker),
    }
