import asyncio
from dataclasses import dataclass
from typing import Iterable, Optional

from playwright.async_api import Page, async_playwright
from playwright_stealth import Stealth

from elephant.source_registry import SourceAvailability
from elephant.ticker_registry import is_jp_ticker, normalize_ticker


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


async def _new_page():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await Stealth().apply_stealth_async(page)
    return playwright, browser, page


async def _page_has_selector(page: Page, url: str, selector: str, timeout: int = 20000) -> tuple[bool, Optional[str]]:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector(selector, timeout=timeout)
        return True, None
    except Exception as exc:
        return False, str(exc)


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
        source_symbol = normalize_ticker(ticker).lower().replace(".", "-")
        return [f"https://www.fool.com/quote/{exchange}/{source_symbol}/" for exchange in ["nasdaq", "nyse", "amex"]]

    async def check_availability(self, ticker: str) -> SourceAvailability:
        canonical = normalize_ticker(ticker.strip().upper())
        source_symbol = canonical.lower().replace(".", "-")
        if _market(canonical) not in self.supports_markets:
            return SourceAvailability(canonical, self.source_id, "unavailable", source_symbol=source_symbol, urls=[])

        playwright, browser, page = await _new_page()
        try:
            last_error = None
            for url in self.urls_for(canonical):
                ok, error = await _page_has_selector(page, url, "h2, h3")
                if ok:
                    found = await page.evaluate(
                        """(ticker) => Array.from(document.querySelectorAll('h2, h3')).some(el =>
                            el.textContent.trim().toLowerCase() === `${ticker.toLowerCase()} news`
                        )""",
                        canonical,
                    )
                    if found:
                        return SourceAvailability(canonical, self.source_id, "available", source_symbol, [url])
                last_error = error
            return SourceAvailability(canonical, self.source_id, "unavailable", source_symbol, [], error=last_error)
        finally:
            await browser.close()
            await playwright.stop()


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
        return source_symbol, f"https://us.minkabu.jp/stock/{source_symbol}"

    async def check_availability(self, ticker: str) -> SourceAvailability:
        canonical = normalize_ticker(ticker.strip().upper())
        source_symbol, base_url = self.url_for(canonical)
        playwright, browser, page = await _new_page()
        try:
            ok, error = await _page_has_selector(page, f"{base_url}/analysis", "#contents")
            if not ok:
                return SourceAvailability(canonical, self.source_id, "unavailable", source_symbol, [], error=error)
            html = await page.locator("#contents").inner_html()
            if "ページが見つかりませんでした" in html or "404 Not Found" in html:
                return SourceAvailability(canonical, self.source_id, "unavailable", source_symbol, [], error="not found")
            return SourceAvailability(canonical, self.source_id, "available", source_symbol, [base_url])
        finally:
            await browser.close()
            await playwright.stop()


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
        playwright, browser, page = await _new_page()
        try:
            ok, error = await _page_has_selector(
                page,
                url,
                "[class*='_EvaluationGraph__graph_'], [class*='_InfiniteBbsList__item_']",
            )
            return SourceAvailability(canonical, self.source_id, "available" if ok else "unavailable", canonical, [url] if ok else [], error=error)
        finally:
            await browser.close()
            await playwright.stop()


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
