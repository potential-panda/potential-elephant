import os
from datetime import datetime

import pandas as pd

from elephant.config import DATA_DIR, TICKERS_FILE, TICKERS_US_FILE
from elephant.ticker_registry import is_jp_ticker, load_cache, load_us_tickers


def get_tickers() -> list[dict]:
    cache = load_cache(TICKERS_FILE)
    us_status = load_us_tickers(TICKERS_FILE)

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

    # JP tickers come only from tickers.txt (rank file). US tickers come only
    # from tickers-us.txt plus any not-yet-confirmed US ticker already seen in
    # the cache (e.g. mid-probe) — never the other way around.
    jp_tickers = set(rank_map)
    us_tickers = {t for t in (set(cache) | set(us_status)) if not is_jp_ticker(t)}

    def build_row(ticker: str) -> dict:
        entry = cache.get(ticker) or {}
        if isinstance(entry, str):
            entry = {"last_seen": entry, "speed_history": []}
        us_entry = us_status.get(ticker)
        return {
            "ticker": ticker,
            "bbs_rank": rank_map.get(ticker),
            "last_seen": entry.get("last_seen"),
            "last_scraped_at": entry.get("last_scraped_at"),
            "speed_history": entry.get("speed_history", []),
            "datasets": avail.get(ticker, {}),
            "in_tickers_us_file": ticker in us_status,
            "us_bbs": us_entry.get("bbs") if us_entry else None,
            "us_minkabu": us_entry.get("minkabu") if us_entry else None,
        }

    jp_items = sorted((build_row(t) for t in jp_tickers), key=lambda x: x["bbs_rank"] or 9999)
    us_items = sorted((build_row(t) for t in us_tickers), key=lambda x: x["ticker"])

    return {
        "jp_items": jp_items,
        "us_items": us_items,
        "tickers_file": TICKERS_FILE,
        "cache_file": TICKERS_FILE.replace("tickers.txt", "tickers.cache.json"),
        "tickers_us_file": TICKERS_US_FILE,
    }
