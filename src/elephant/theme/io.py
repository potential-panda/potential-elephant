from __future__ import annotations

import glob
import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from elephant.config import DATA_DIR
from elephant.framework import HarvesterResult, Store
from elephant.theme.catalog import get_etf_theme_source, list_theme_definitions, list_theme_sources
from elephant.ticker_registry import normalize_ticker


TODAY = datetime.now().strftime("%Y-%m-%d")


def row_id(*parts) -> str:
    return hashlib.md5("|".join(str(part) for part in parts).encode()).hexdigest()


def _jsonable(value):
    if isinstance(value, (list, tuple, dict)):
        return value
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return value


def _read_dataset(dataset: str, data_dir: str = DATA_DIR) -> pd.DataFrame:
    files = glob.glob(os.path.join(data_dir, f"dataset={dataset}", "**", "data.parquet"), recursive=True)
    frames = []
    for file in files:
        try:
            frames.append(pd.read_parquet(file))
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _read_latest_dataset(dataset: str, data_dir: str = DATA_DIR) -> pd.DataFrame:
    file = latest_dataset_path(dataset, data_dir)
    if not file:
        return pd.DataFrame()
    try:
        return pd.read_parquet(file)
    except Exception:
        return pd.DataFrame()


def load_theme_members(data_dir: str = DATA_DIR) -> pd.DataFrame:
    return _read_dataset("theme_members", data_dir)


def load_theme_source_themes(data_dir: str = DATA_DIR) -> pd.DataFrame:
    return _read_dataset("theme_source_themes", data_dir)


def load_etf_holdings(data_dir: str = DATA_DIR) -> pd.DataFrame:
    return _read_dataset("etf_holdings", data_dir)


def load_ticker_theme_scores(data_dir: str = DATA_DIR) -> pd.DataFrame:
    return _read_latest_dataset("ticker_theme_scores", data_dir)


def load_river_suggestions(data_dir: str = DATA_DIR) -> pd.DataFrame:
    return _read_latest_dataset("river_suggestions", data_dir)


def save_theme_definitions(data_dir: str = DATA_DIR) -> int:
    store = Store(data_dir)
    rows = []
    for theme in list_theme_definitions():
        row = theme.to_dict()
        row["id"] = row_id("theme_definition", theme.theme_id)
        row["date"] = TODAY
        rows.append(row)
    store.save("theme_definitions", HarvesterResult(tags={"date": TODAY}, data=rows))
    return len(rows)


def save_theme_sources(data_dir: str = DATA_DIR) -> int:
    rows = []
    for source in list_theme_sources(enabled_only=False):
        row = source.to_dict()
        row["id"] = row_id("theme_source", source.source_id)
        row["date"] = TODAY
        rows.append(row)
    Store(data_dir).save("theme_sources", HarvesterResult(tags={"date": TODAY}, data=rows))
    return len(rows)


def import_theme_members_csv(csv_path: str, data_dir: str = DATA_DIR) -> int:
    df = pd.read_csv(csv_path)
    if "theme_id" not in df.columns or "ticker" not in df.columns:
        raise ValueError("theme member CSV requires theme_id and ticker columns")
    rows = []
    for _, raw in df.iterrows():
        theme_id = str(raw.get("theme_id", "")).strip()
        ticker = normalize_ticker(str(raw.get("ticker", "")).strip().upper())
        if not theme_id or not ticker:
            continue
        source = str(_jsonable(raw.get("source")) or "csv")
        source_url = str(_jsonable(raw.get("source_url")) or "")
        row = {
            "id": row_id("theme_member", theme_id, ticker, source, source_url),
            "theme_id": theme_id,
            "ticker": ticker,
            "name": str(_jsonable(raw.get("name")) or ""),
            "source": source,
            "source_url": source_url,
            "raw_rank": _jsonable(raw.get("raw_rank")),
            "source_weight": _jsonable(raw.get("source_weight")) or 1.0,
            "theme_purity": _jsonable(raw.get("theme_purity")) or "",
            "harvested_at": datetime.now().isoformat(timespec="seconds"),
        }
        rows.append(row)
    Store(data_dir).save("theme_members", HarvesterResult(tags={"date": TODAY}, data=rows))
    return len(rows)


def import_etf_holdings_csv(csv_path: str, data_dir: str = DATA_DIR) -> int:
    df = pd.read_csv(csv_path)
    if "ticker" not in df.columns:
        raise ValueError("ETF holdings CSV requires ticker column")
    if "etf" not in df.columns and "fund" not in df.columns:
        raise ValueError("ETF holdings CSV requires etf or fund column")

    rows = []
    for _, raw in df.iterrows():
        etf = str(raw.get("etf", raw.get("fund", ""))).strip().upper()
        ticker = normalize_ticker(str(raw.get("ticker", "")).strip().upper())
        if not etf or not ticker:
            continue
        mapped = get_etf_theme_source(etf)
        theme_id = str(raw.get("theme_id") or (mapped.theme_id if mapped else "") or "").strip()
        if not theme_id:
            continue
        row = {
            "id": row_id("etf_holding", etf, theme_id, ticker),
            "etf": etf,
            "theme_id": theme_id,
            "ticker": ticker,
            "name": str(_jsonable(raw.get("name")) or ""),
            "holding_weight": _jsonable(raw.get("holding_weight", raw.get("weight"))) or "",
            "issuer": str(_jsonable(raw.get("issuer")) or (mapped.issuer if mapped else "") or ""),
            "source_url": str(_jsonable(raw.get("source_url")) or ""),
            "as_of": str(_jsonable(raw.get("as_of")) or TODAY),
            "theme_purity": _jsonable(raw.get("theme_purity")) or (mapped.theme_purity if mapped else "") or "",
            "issuer_quality": _jsonable(raw.get("issuer_quality")) or (mapped.issuer_quality if mapped else 1.0),
            "harvested_at": datetime.now().isoformat(timespec="seconds"),
        }
        rows.append(row)
    Store(data_dir).save("etf_holdings", HarvesterResult(tags={"date": TODAY}, data=rows))
    return len(rows)


def clear_dataset_partition(dataset: str, data_dir: str = DATA_DIR, date: str | None = None) -> None:
    date = date or TODAY
    path = Path(data_dir) / f"dataset={dataset}" / f"date={date}"
    if path.exists():
        shutil.rmtree(path)


def write_dataset(
    dataset: str,
    rows: list[dict],
    data_dir: str = DATA_DIR,
    date: str | None = None,
    *,
    replace: bool = False,
) -> int:
    date = date or TODAY
    if replace:
        clear_dataset_partition(dataset, data_dir, date)
    Store(data_dir).save(dataset, HarvesterResult(tags={"date": date}, data=rows))
    return len(rows)


def latest_dataset_path(dataset: str, data_dir: str = DATA_DIR) -> Path | None:
    files = sorted(Path(data_dir).glob(f"dataset={dataset}/date=*/data.parquet"), reverse=True)
    return files[0] if files else None
