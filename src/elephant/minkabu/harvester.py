import hashlib
import re
from datetime import datetime
from typing import Optional

from elephant.framework import Harvester, HarvesterResult, Store
from elephant.web_client import open_web_page, visit_page


def generate_id(*args):
    content = "|".join(str(arg) for arg in args)
    return hashlib.md5(content.encode()).hexdigest()


class MinkabuHarvester(Harvester):
    def __init__(self, store: Store, ticker: str, tickers_file: str = None):
        super().__init__(store)
        from elephant.ticker_registry import normalize_ticker
        self.ticker = normalize_ticker(ticker)
        self.tickers_file = tickers_file
        self.is_jp = self.ticker.endswith(".T")
        self.minkabu_ticker = self.ticker.replace(".T", "") if self.is_jp else self.ticker
        self.minkabu_base = "https://minkabu.jp" if self.is_jp else "https://us.minkabu.jp"

    def get_url(self, params: dict) -> str:
        if params.get("source_url"):
            return params["source_url"]
        path = "stock" if self.is_jp else "stocks"
        return f"{self.minkabu_base}/{path}/{self.minkabu_ticker}"

    def _clean_html(self, html: str) -> str:
        """Remove noise to save tokens/storage for later LLM parsing."""
        if not html:
            return ""

        # Remove scripts, styles, and SVG blocks
        html = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.DOTALL)
        html = re.sub(r"<style.*?>.*?</style>", "", html, flags=re.DOTALL)
        html = re.sub(r"<svg.*?>.*?</svg>", "", html, flags=re.DOTALL)
        html = re.sub(r"<noscript.*?>.*?</noscript>", "", html, flags=re.DOTALL)

        # Collapse multiple whitespaces and newlines
        html = re.sub(r"\s+", " ", html).strip()
        return html

    _ERROR_PHRASES = ["ページが見つかりませんでした", "404 Not Found"]

    async def _get_page_content(self, page, url: str) -> Optional[str]:
        try:
            await visit_page(page, url, jitter=(3, 8), label="Minkabu")
            # Wait for #contents container as per spec
            await page.wait_for_selector("#contents", timeout=30000)
            container = await page.query_selector("#contents")
            if container:
                raw_html = await container.inner_html()
                if any(phrase in raw_html for phrase in self._ERROR_PHRASES):
                    print(f"404/not-found page detected for {url}, skipping.")
                    return None
                return self._clean_html(raw_html)
            return None
        except Exception as e:
            print(f"Error loading {url}: {e}")
            return None

    async def scrape(self, url: str, params: dict) -> dict[str, HarvesterResult]:
        async with open_web_page() as page:

            scraped_at = datetime.now()

            sub_pages = ["analysis", "research", "pick", "analyst_consensus"]
            data_record = {
                "id": generate_id(self.ticker, scraped_at.strftime("%Y-%m-%d"), "minkabu_combined"),
                "ticker": self.ticker,
                "scraped_at": scraped_at,
            }

            found_any = False
            base_url = params.get("source_url") or url
            for sub in sub_pages:
                target_url = f"{base_url.rstrip('/')}/{sub}"
                content = await self._get_page_content(page, target_url)
                data_record[sub] = content if content else ""
                if content:
                    found_any = True

            if not self.is_jp and self.tickers_file:
                from elephant.ticker_registry import mark_minkabu_us
                mark_minkabu_us(self.tickers_file, self.ticker, found_any)

            results = {}
            if found_any:
                results["minkabu_raw_html"] = HarvesterResult(
                    tags={"ticker": self.ticker, "YEAR": scraped_at.strftime("%Y")}, data=[data_record]
                )
            return results
