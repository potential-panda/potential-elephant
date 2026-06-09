import os
from datetime import datetime, timedelta

import pandas as pd

DATA_DIR = "/panda-infra/elephant"


def _load_prices(ticker: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "dataset=daily_prices", f"ticker={ticker}", "data.parquet")
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_parquet(path)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date")
    except Exception:
        return pd.DataFrame()


def _pct_change(df: pd.DataFrame, days: int) -> float | None:
    if df.empty:
        return None
    latest_date = df["date"].max()
    cutoff = latest_date - timedelta(days=days)
    past = df[df["date"] <= cutoff]
    if past.empty:
        return None
    start_close = float(past.iloc[-1]["close"])
    end_close = float(df.iloc[-1]["close"])
    if start_close == 0:
        return None
    return round((end_close - start_close) / start_close * 100, 2)


def get_price_changes(tickers: list[str]) -> dict:
    result = {}
    for ticker in tickers:
        df = _load_prices(ticker)
        result[ticker] = {
            "1m":  _pct_change(df, 30),
            "3m":  _pct_change(df, 90),
            "6m":  _pct_change(df, 180),
            "1y":  _pct_change(df, 365),
            "last_close": float(df.iloc[-1]["close"]) if not df.empty else None,
            "last_date":  df.iloc[-1]["date"].strftime("%Y-%m-%d") if not df.empty else None,
        }
    return result
