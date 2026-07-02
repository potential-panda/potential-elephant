import glob
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from elephant.config import DATA_DIR, TICKERS_FILE
from elephant.ticker_registry import get_speed_history, normalize_ticker


def _repair_mojibake(value):
    if not isinstance(value, str) or not value:
        return value
    try:
        repaired = value.encode("latin1").decode("utf-8", errors="ignore")
    except Exception:
        return value
    return repaired or value


def _read_latest_ticker_dataset(dataset: str, ticker: str, data_dir: str = DATA_DIR) -> pd.DataFrame:
    canonical = normalize_ticker(ticker)
    pattern = os.path.join(data_dir, f"dataset={dataset}", f"ticker={canonical}", "**", "data.parquet")
    files = glob.glob(pattern, recursive=True)
    if not files:
        return pd.DataFrame()
    frames = []
    for file in files:
        try:
            frames.append(pd.read_parquet(file))
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_yjp_evaluations(ticker: str, data_dir: str = DATA_DIR) -> pd.DataFrame:
    return _read_latest_ticker_dataset("yahoo_evaluations", ticker, data_dir)


def load_yjp_comments(ticker: str, data_dir: str = DATA_DIR) -> pd.DataFrame:
    return _read_latest_ticker_dataset("yahoo_comments", ticker, data_dir)


def load_prices(ticker: str, data_dir: str = DATA_DIR) -> pd.DataFrame:
    return _read_latest_ticker_dataset("daily_prices", ticker, data_dir)


def load_minkabu(ticker: str, data_dir: str = DATA_DIR) -> pd.DataFrame:
    return _read_latest_ticker_dataset("minkabu_raw_html", ticker, data_dir)


def load_news_for_ticker(ticker: str, days: int = 14, data_dir: str = DATA_DIR) -> pd.DataFrame:
    canonical = normalize_ticker(ticker)
    bare = canonical[:-2] if canonical.endswith(".T") else canonical
    files = glob.glob(os.path.join(data_dir, "dataset=news_headlines", "date=*", "data.parquet"))
    if not files:
        return pd.DataFrame()
    frames = []
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=days), tz="UTC")
    for file in files:
        try:
            df = pd.read_parquet(file)
            if "published" in df.columns:
                df["published_dt"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
                df = df[df["published_dt"].isna() | (df["published_dt"] >= cutoff)]
            mask = df.get("title", pd.Series(dtype=str)).fillna("").str.contains(bare, case=False, na=False)
            if "summary" in df.columns:
                mask |= df["summary"].fillna("").str.contains(bare, case=False, na=False)
            if "ticker" in df.columns:
                mask |= df["ticker"].fillna("").str.upper().eq(bare.upper())
            frames.append(df[mask])
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_tdnet_for_ticker(ticker: str, days: int = 14, data_dir: str = DATA_DIR) -> pd.DataFrame:
    canonical = normalize_ticker(ticker)
    files = glob.glob(os.path.join(data_dir, "dataset=tdnet_disclosures", "date=*", "data.parquet"))
    if not files:
        return pd.DataFrame()
    frames = []
    cutoff = datetime.now() - timedelta(days=days)
    for file in files:
        try:
            df = pd.read_parquet(file)
            if "date" in df.columns:
                df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
                df = df[df["date_dt"].isna() | (df["date_dt"] >= cutoff)]
            if "ticker" in df.columns:
                frames.append(df[df["ticker"].fillna("").str.upper().eq(canonical.upper())])
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].map(_repair_mojibake)
    return df


def load_speed_history(ticker: str, tickers_file: str = TICKERS_FILE) -> list[dict]:
    return get_speed_history(tickers_file, normalize_ticker(ticker))
