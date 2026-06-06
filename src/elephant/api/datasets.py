import glob
import os
from datetime import datetime, timedelta

import pandas as pd

DATA_DIR = "/panda-infra/elephant"
DATASETS = ["yahoo_comments", "yahoo_evaluations", "minkabu_raw_html", "news_headlines", "tdnet_disclosures"]


def get_stats() -> list[dict]:
    results = []
    for dataset in DATASETS:
        pattern = os.path.join(DATA_DIR, f"dataset={dataset}", "**", "data.parquet")
        files = glob.glob(pattern, recursive=True)
        total_records = 0
        total_size = 0
        tickers = set()
        latest_date = None
        earliest_date = None

        for f in files:
            try:
                size = os.path.getsize(f)
                total_size += size
                df = pd.read_parquet(f, columns=["scraped_at"] + (["ticker"] if dataset != "news_headlines" and dataset != "tdnet_disclosures" else []))
                total_records += len(df)
                if "ticker" in df.columns:
                    tickers.update(df["ticker"].dropna().unique())
                dates = pd.to_datetime(df["scraped_at"])
                d_max = dates.max()
                d_min = dates.min()
                if latest_date is None or d_max > latest_date:
                    latest_date = d_max
                if earliest_date is None or d_min < earliest_date:
                    earliest_date = d_min
            except Exception:
                pass

        results.append({
            "dataset": dataset,
            "files": len(files),
            "records": total_records,
            "tickers": len(tickers),
            "size_mb": round(total_size / 1024 / 1024, 2),
            "latest": latest_date.isoformat() if latest_date else None,
            "earliest": earliest_date.isoformat() if earliest_date else None,
        })

    return results


def query_dataset(dataset: str, ticker: str = None, keyword: str = None, limit: int = 50) -> list[dict]:
    if dataset == "news_headlines":
        pattern = os.path.join(DATA_DIR, "dataset=news_headlines", "date=*", "data.parquet")
        files = sorted(glob.glob(pattern), reverse=True)
        dfs = []
        for f in files[:7]:
            try:
                dfs.append(pd.read_parquet(f))
            except Exception:
                pass
        if not dfs:
            return []
        df = pd.concat(dfs, ignore_index=True)
        df["scraped_at"] = pd.to_datetime(df["scraped_at"])
        df = df.sort_values("scraped_at", ascending=False)
        if keyword:
            mask = df["title"].str.contains(keyword, case=False, na=False)
            if "summary" in df.columns:
                mask |= df["summary"].fillna("").str.contains(keyword, case=False, na=False)
            df = df[mask]
        return df.head(limit).fillna("").astype(str).to_dict("records")

    if not ticker:
        return []
    if not ticker.endswith(".T"):
        ticker = f"{ticker}.T"

    pattern = os.path.join(DATA_DIR, f"dataset={dataset}", f"ticker={ticker}", "**", "data.parquet")
    files = glob.glob(pattern, recursive=True)
    if not files:
        return []
    dfs = [pd.read_parquet(f) for f in files]
    df = pd.concat(dfs, ignore_index=True).sort_values("scraped_at", ascending=False)
    return df.head(limit).fillna("").astype(str).to_dict("records")
