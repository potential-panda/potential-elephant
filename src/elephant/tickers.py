import logging
import os
import random


def get_tickers(tickers_file: str, num: int = None):
    """
    Read tickers from a file.
    If num is provided, return num random tickers.
    Otherwise, return all tickers.
    """
    if not os.path.exists(tickers_file):
        logging.error(f"{tickers_file} not found.")
        return []

    with open(tickers_file, "r") as f:
        tickers = [line.strip() for line in f if line.strip()]

    if num is not None:
        return random.sample(tickers, min(num, len(tickers)))

    return tickers
