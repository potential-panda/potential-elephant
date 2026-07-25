import asyncio
from dataclasses import dataclass
from typing import Iterable

from elephant.source_registry import SourceAvailability
from elephant.source.fool_urls import fool_quote_urls
from elephant.ticker_registry import is_jp_ticker, normalize_ticker
from elephant.web_client import open_web_page, page_has_selector, visit_page


@dataclass(frozen=True)
class SourceAdapter:
    source_id: str
    supports_markets: set[str]
    harvest_cadence: str = "daily"
    max_parallel: int = 1
    min_spacing_minutes: int = 5

    async def check_availability(self, ticker: str) -> SourceAvailability:
        raise NotImplementedError


def _market(ticker: str) -> str:
    return "JP" if is_jp_ticker(ticker) else "US"


class FoolQuoteNewsAdapter(SourceAdapter):
    def __init__(self):
        super().__init__(
            source_id="fool_quote_news",
            supports_markets={"US"},
            harvest_cadence="3x_daily",
            max_parallel=1,
            min_spacing_minutes=3,
        )

    def urls_for(self, ticker: str) -> list[str]:
        return fool_quote_urls(ticker)[1]

    async def check_availability(self, ticker: str) -> SourceAvailability:
        canonical = normalize_ticker(ticker.strip().upper())
        source_symbol = canonical.lower().replace(".", "-")
        if _market(canonical) not in self.supports_markets:
            return SourceAvailability(canonical, self.source_id, "unavailable", source_symbol=source_symbol, urls=[])

        async with open_web_page(locale="en-US", timezone_id="America/New_York") as page:
            last_error = None
            for url in self.urls_for(canonical):
                ok, error = await page_has_selector(page, url, "h2, h3")
                if ok:
                    found = await page.evaluate(
                        """(ticker) => Array.from(document.querySelectorAll('h2, h3')).some(el =>
                            el.textContent.trim().toCapacityCase() === `${ticker.toCapacityCase()} news`
                        )""",
                        canonical,
                    )
                    if found:
                        return SourceAvailability(canonical, self.source_id, "available", source_symbol, [url])
                last_error = error
            return SourceAvailability(canonical, self.source_id, "unavailable", source_symbol, [], error=last_error)


class MinkabuAdapter(SourceAdapter):
    def __init__(self):
        super().__init__(
            source_id="minkabu",
            supports_markets={"JP", "US"},
            harvest_cadence="daily",
            max_parallel=1,
            min_spacing_minutes=5,
        )

    def url_for(self, ticker: str) -> tuple[str, str]:
        canonical = normalize_ticker(ticker.strip().upper())
        if is_jp_ticker(canonical):
            source_symbol = canonical.replace(".T", "")
            return source_symbol, f"https://minkabu.jp/stock/{source_symbol}"
        source_symbol = canonical
        return source_symbol, f"https://us.minkabu.jp/stocks/{source_symbol}"

    async def check_availability(self, ticker: str) -> SourceAvailability:
        canonical = normalize_ticker(ticker.strip().upper())
        source_symbol, base_url = self.url_for(canonical)
        if not is_jp_ticker(canonical):
            return SourceAvailability(canonical, self.source_id, "available", source_symbol, [base_url])
        async with open_web_page() as page:
            probe_urls = [base_url, f"{base_url}/analysis"]
            last_error = None
            for url in probe_urls:
                try:
                    response = await visit_page(page, url)
                    if response and response.status >= 400:
                        last_error = f"HTTP {response.status}"
                        continue
                    try:
                        await page.wait_for_selector("#contents", timeout=20000)
                    except Exception as exc:
                        last_error = str(exc)
                        continue
                    html = await page.locator("#contents").inner_html()
                    if "ページが見つかりませんでした" in html or "404 Not Found" in html:
                        last_error = "not found"
                        continue
                    body = await page.locator("body").inner_text(timeout=5000)
                    if "株価" in body or "予想" in body or "アナリスト" in body or "個人予想" in body:
                        return SourceAvailability(canonical, self.source_id, "available", source_symbol, [url])
                    last_error = "page content missing stock markers"
                except Exception as exc:
                    last_error = str(exc)
            return SourceAvailability(canonical, self.source_id, "unavailable", source_symbol, [], error=last_error)


class YahooJpBbsAdapter(SourceAdapter):
    def __init__(self):
        super().__init__(
            source_id="yahoo_jp_bbs",
            supports_markets={"JP", "US"},
            harvest_cadence="daily",
            max_parallel=1,
            min_spacing_minutes=5,
        )

    def url_for(self, ticker: str) -> tuple[str, str]:
        canonical = normalize_ticker(ticker.strip().upper())
        return canonical, f"https://finance.yahoo.co.jp/quote/{canonical}/forum"

    async def check_availability(self, ticker: str) -> SourceAvailability:
        canonical, url = self.url_for(ticker)
        async with open_web_page() as page:
            ok, error = await page_has_selector(
                page,
                url,
                "[class*='_EvaluationGraph__graph_'], [class*='_InfiniteBbsList__item_']",
            )
            return SourceAvailability(canonical, self.source_id, "available" if ok else "unavailable", canonical, [url] if ok else [], error=error)


ADAPTERS = {
    "fool_quote_news": FoolQuoteNewsAdapter(),
    "minkabu": MinkabuAdapter(),
    "yahoo_jp_bbs": YahooJpBbsAdapter(),
}


def get_adapters(source_id: str | None = None) -> Iterable[SourceAdapter]:
    if source_id:
        adapter = ADAPTERS.get(source_id)
        if not adapter:
            raise ValueError(f"Unknown source: {source_id}")
        return [adapter]
    return ADAPTERS.values()


async def check_sources(tickers: list[str], source_id: str | None = None) -> list[SourceAvailability]:
    results = []
    for ticker in tickers:
        canonical = normalize_ticker(ticker.strip().upper())
        for adapter in get_adapters(source_id):
            if _market(canonical) not in adapter.supports_markets:
                continue
            results.append(await adapter.check_availability(canonical))
            await asyncio.sleep(0.2)
    return results
