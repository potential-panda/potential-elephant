import json
import logging
import os
import random


def get_tickers(tickers_file: str, num: int = None, atlas_path: str = None):
    """
    Read tickers from a file, optionally merged with atlas companies.
    If num is provided, return num random tickers from the merged set.
    """
    from elephant.ticker_registry import normalize_ticker

    tickers: list[str] = []

    if os.path.exists(tickers_file):
        with open(tickers_file, "r") as f:
            tickers = [line.strip() for line in f if line.strip()]
    else:
        logging.error(f"{tickers_file} not found.")

    if atlas_path and os.path.exists(atlas_path):
        try:
            with open(atlas_path, encoding="utf-8") as f:
                data = json.load(f)
            atlas_tickers = {
                normalize_ticker(company["ticker"])
                for value_chain in data.get("value_chains", [])
                for company in value_chain.get("companies", [])
            }
            existing = set(tickers)
            tickers = tickers + [t for t in sorted(atlas_tickers) if t not in existing]
        except Exception:
            logging.exception(f"Failed to load atlas tickers from {atlas_path}")

    if num is not None:
        return random.sample(tickers, min(num, len(tickers)))

    return tickers
