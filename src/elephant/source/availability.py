from elephant.source.catalog import get_source, list_sources
from elephant.source.registry import SourceAvailability, SourceRegistry
from elephant.source.run_log import finish_run, start_run
from elephant.source.tickers import known_tickers, market_for_ticker
from elephant.ticker_registry import normalize_ticker


def source_symbol_and_urls(source_id: str, ticker: str) -> tuple[str, list[str]]:
    canonical = normalize_ticker(str(ticker).strip().upper())
    if source_id == "minkabu":
        if canonical.endswith(".T"):
            symbol = canonical.replace(".T", "")
            return symbol, [f"https://minkabu.jp/stock/{symbol}"]
        return canonical, [f"https://us.minkabu.jp/stock/{canonical}"]
    if source_id == "yahoo_jp_bbs":
        return canonical, [f"https://finance.yahoo.co.jp/quote/{canonical}/forum"]
    if source_id == "fool_quote_news":
        symbol = canonical.lower().replace(".", "-")
        return symbol, [f"https://www.fool.com/quote/{exchange}/{symbol}/" for exchange in ("nasdaq", "nyse", "amex")]
    if source_id == "daily_prices":
        return canonical, [f"yfinance://{canonical}"]
    raise ValueError(f"No ticker URL resolver for source: {source_id}")


async def _check_with_existing_adapter(source_id: str, ticker: str) -> SourceAvailability:
    # Compatibility wrapper around existing implementation while v2 stabilizes.
    from elephant.source_adapters import ADAPTERS

    adapter = ADAPTERS[source_id]
    old = await adapter.check_availability(ticker)
    return SourceAvailability(
        ticker=old.ticker,
        source_id=old.source_id,
        status=old.status,
        source_symbol=old.source_symbol,
        urls=old.urls,
        checked_at=old.checked_at,
        error=old.error,
    )


async def check_ticker_source(ticker: str, source_id: str, registry: SourceRegistry | None = None) -> SourceAvailability:
    source = get_source(source_id)
    canonical = normalize_ticker(str(ticker).strip().upper())
    market = market_for_ticker(canonical)
    if source.scope != "ticker":
        raise ValueError(f"{source_id} is not a ticker-scoped source")
    if market not in source.markets:
        symbol, _urls = source_symbol_and_urls(source_id, canonical)
        return SourceAvailability(canonical, source_id, "unavailable", source_symbol=symbol, urls=[], error="unsupported market")

    run = start_run("availability_check", source_id, source.scope, canonical)
    try:
        if not source.availability_check_required:
            symbol, urls = source_symbol_and_urls(source_id, canonical)
            availability = SourceAvailability(canonical, source_id, "available", symbol, urls)
        else:
            availability = await _check_with_existing_adapter(source_id, canonical)
        if registry:
            registry.upsert_availability(availability)
            registry.save()
        finish_run(run, "ok", row_count=1 if availability.status == "available" else 0, error=availability.error)
        return availability
    except Exception as exc:
        finish_run(run, "error", error=str(exc))
        symbol, _urls = source_symbol_and_urls(source_id, canonical)
        availability = SourceAvailability(canonical, source_id, "unavailable", symbol, [], error=str(exc))
        if registry:
            registry.upsert_availability(availability)
            registry.save()
        return availability


async def check_sources(
    tickers: list[str] | None = None,
    source_id: str | None = None,
    registry: SourceRegistry | None = None,
) -> list[SourceAvailability]:
    registry = registry or SourceRegistry()
    tickers = tickers or known_tickers()
    sources = [get_source(source_id)] if source_id else list_sources(scope="ticker")
    results = []
    for ticker in tickers:
        canonical = normalize_ticker(str(ticker).strip().upper())
        for source in sources:
            if not source.enabled or source.scope != "ticker":
                continue
            if market_for_ticker(canonical) not in source.markets:
                continue
            results.append(await check_ticker_source(canonical, source.source_id, registry))
    return results

