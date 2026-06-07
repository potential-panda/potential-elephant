import os
from datetime import datetime

import pandas as pd

from elephant.ticker_registry import load_cache

DATA_DIR = "/panda-infra/elephant"
TICKERS_FILE = "/panda-infra/elephant/tickers.txt"


def get_tickers() -> list[dict]:
    cache = load_cache(TICKERS_FILE)

    # BBS rank order from tickers.txt
    rank_map = {}
    try:
        with open(TICKERS_FILE) as f:
            for i, line in enumerate(f, 1):
                t = line.strip()
                if t:
                    rank_map[t] = i
    except FileNotFoundError:
        pass

    # Dataset availability: latest scraped_at per ticker per dataset
    avail: dict[str, dict] = {}
    datasets = ["yahoo_comments", "yahoo_evaluations", "minkabu_raw_html"]
    for dataset in datasets:
        import glob
        pattern = os.path.join(DATA_DIR, f"dataset={dataset}", "ticker=*", "**", "data.parquet")
        for f in glob.glob(pattern, recursive=True):
            ticker = f.split(f"dataset={dataset}/ticker=")[1].split("/")[0]
            try:
                df = pd.read_parquet(f, columns=["scraped_at"])
                latest = pd.to_datetime(df["scraped_at"]).max()
                if ticker not in avail:
                    avail[ticker] = {}
                prev = avail[ticker].get(dataset)
                if prev is None or latest > prev:
                    avail[ticker][dataset] = latest.isoformat()
            except Exception:
                pass

    result = []
    all_tickers = set(rank_map) | set(cache)
    for ticker in all_tickers:
        entry = cache.get(ticker) or {}
        if isinstance(entry, str):
            entry = {"last_seen": entry, "speed_history": []}
        result.append({
            "ticker": ticker,
            "bbs_rank": rank_map.get(ticker),
            "last_seen": entry.get("last_seen"),
            "last_scraped_at": entry.get("last_scraped_at"),
            "speed_history": entry.get("speed_history", []),
            "datasets": avail.get(ticker, {}),
        })

    result.sort(key=lambda x: (x["bbs_rank"] or 9999))
    return {
        "items": result,
        "tickers_file": TICKERS_FILE,
        "cache_file": TICKERS_FILE.replace("tickers.txt", "tickers.cache.json"),
    }
