from elephant.config import TICKERS_FILE, TREE_PATH
from elephant.ticker_registry import is_jp_ticker, load_cache, load_us_tickers, normalize_ticker
from elephant.tickers import get_tickers


def market_for_ticker(ticker: str) -> str:
    return "JP" if is_jp_ticker(normalize_ticker(ticker)) else "US"


def known_tickers(tickers_file: str = TICKERS_FILE, tree_path: str = TREE_PATH) -> list[str]:
    seen = set()
    result = []
    for ticker in get_tickers(tickers_file, tree_path=tree_path):
        canonical = normalize_ticker(str(ticker).strip().upper())
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def all_known_tickers(tickers_file: str = TICKERS_FILE, tree_path: str = TREE_PATH) -> list[str]:
    seen = set()
    result = []

    for ticker in known_tickers(tickers_file=tickers_file, tree_path=tree_path):
        if ticker not in seen:
            seen.add(ticker)
            result.append(ticker)

    for ticker in load_cache(tickers_file).keys():
        canonical = normalize_ticker(str(ticker).strip().upper())
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)

    for ticker in load_us_tickers(tickers_file).keys():
        canonical = normalize_ticker(str(ticker).strip().upper())
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)

    try:
        from elephant.source.registry import SourceRegistry

        for ticker in SourceRegistry().tickers():
            canonical = normalize_ticker(str(ticker).strip().upper())
            if canonical and canonical not in seen:
                seen.add(canonical)
                result.append(canonical)
    except Exception:
        pass

    return result
