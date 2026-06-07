import glob
import os
from datetime import datetime, timedelta

import pandas as pd

from elephant.ticker_registry import normalize_ticker

DATA_DIR = "/panda-infra/elephant"


def _normalize(ticker: str) -> tuple[str, str]:
    full = normalize_ticker(ticker.strip())
    bare = full[:-2] if full.endswith(".T") else full
    return full, bare


def get_detail(ticker_raw: str) -> dict:
    ticker_t, bare = _normalize(ticker_raw.strip())
    result: dict = {"ticker": ticker_t, "bare": bare}

    # 1. Dive
    from elephant.api.dive import get_latest as get_dive_latest
    result["dive"] = get_dive_latest(ticker_t)

    # 2. Yahoo comments
    pattern = os.path.join(
        DATA_DIR, "dataset=yahoo_comments", f"ticker={ticker_t}", "**", "data.parquet"
    )
    files = glob.glob(pattern, recursive=True)
    if files:
        try:
            df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
            df["scraped_at"] = pd.to_datetime(df["scraped_at"])
            df = df.sort_values("scraped_at", ascending=False)
            result["comments"] = {
                "total": len(df),
                "records": df.head(50).fillna("").astype(str).to_dict("records"),
            }
        except Exception:
            result["comments"] = None
    else:
        result["comments"] = None

    # 3. Yahoo evaluations
    pattern = os.path.join(
        DATA_DIR, "dataset=yahoo_evaluations", f"ticker={ticker_t}", "**", "data.parquet"
    )
    files = glob.glob(pattern, recursive=True)
    if files:
        try:
            df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
            df["scraped_at"] = pd.to_datetime(df["scraped_at"])
            df = df.sort_values("scraped_at", ascending=False)
            result["evaluations"] = df.head(30).fillna("").astype(str).to_dict("records")
        except Exception:
            result["evaluations"] = None
    else:
        result["evaluations"] = None

    # 4. Minkabu
    year = datetime.now().strftime("%Y")
    minkabu_path = os.path.join(
        DATA_DIR, "dataset=minkabu_raw_html", f"ticker={ticker_t}", f"YEAR={year}", "data.parquet"
    )
    if os.path.exists(minkabu_path):
        try:
            from elephant.synthesizer import _strip_html
            df = pd.read_parquet(minkabu_path).sort_values("scraped_at", ascending=False)
            if not df.empty:
                raw = str(df.iloc[0].get("analyst_consensus", ""))
                text = _strip_html(raw).strip()
                result["minkabu"] = text[:3000] if len(text) > 50 else None
            else:
                result["minkabu"] = None
        except Exception:
            result["minkabu"] = None
    else:
        result["minkabu"] = None

    # 5. Recent news mentioning this ticker
    since = datetime.now() - timedelta(days=7)
    news_files = glob.glob(os.path.join(DATA_DIR, "dataset=news_headlines", "date=*", "data.parquet"))
    if news_files:
        try:
            dfs = [pd.read_parquet(f) for f in news_files]
            combined = pd.concat(dfs, ignore_index=True)
            combined["published_dt"] = pd.to_datetime(combined["published"], errors="coerce", utc=True)
            cutoff = pd.Timestamp(since, tz="UTC")
            combined = combined[combined["published_dt"].isna() | (combined["published_dt"] >= cutoff)]
            mask = combined["title"].str.contains(bare, case=False, na=False)
            if "summary" in combined.columns:
                mask |= combined["summary"].fillna("").str.contains(bare, case=False, na=False)
            matched = (
                combined[mask]
                .sort_values("published_dt", ascending=False)
                .head(20)
                .drop(columns=["published_dt"], errors="ignore")
                .fillna("")
                .astype(str)
            )
            result["news"] = matched.to_dict("records")
        except Exception:
            result["news"] = []
    else:
        result["news"] = []

    return result
