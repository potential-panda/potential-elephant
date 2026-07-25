from __future__ import annotations

from elephant.ticker_registry import normalize_ticker


FOOL_EXCHANGE_OVERRIDES = {
    "COHR": "nyse",
}

FOOL_EXCHANGES = ("nasdaq", "nyse", "amex")


def fool_quote_urls(ticker: str) -> tuple[str, list[str]]:
    canonical = normalize_ticker(str(ticker).strip().upper())
    symbol = canonical.lower().replace(".", "-")
    override = FOOL_EXCHANGE_OVERRIDES.get(canonical)
    exchanges = (override,) if override else FOOL_EXCHANGES
    return symbol, [f"https://www.fool.com/quote/{exchange}/{symbol}/" for exchange in exchanges]
