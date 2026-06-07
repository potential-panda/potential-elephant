import asyncio
import hashlib
import random
import re
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from elephant.framework import Harvester, HarvesterResult, Store


def generate_id(*args):
    content = "|".join(str(arg) for arg in args)
    return hashlib.md5(content.encode()).hexdigest()


class MinkabuHarvester(Harvester):
    def __init__(self, store: Store, ticker: str):
        super().__init__(store)
        from elephant.ticker_registry import normalize_ticker
        self.ticker = normalize_ticker(ticker)
        self.minkabu_ticker = self.ticker.replace(".T", "") if self.ticker.endswith(".T") else self.ticker

    def get_url(self, params: dict) -> str:
        # This harvester visits multiple URLs, so we return the base one for reference
        return f"https://minkabu.jp/stock/{self.minkabu_ticker}"

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
        wait_time = random.uniform(3, 8)
        print(f"Waiting {wait_time:.2f} seconds before loading {url}...")
        await asyncio.sleep(wait_time)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
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
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            scraped_at = datetime.now()

            sub_pages = ["analysis", "research", "pick", "analyst_consensus"]
            data_record = {
                "id": generate_id(self.ticker, scraped_at.strftime("%Y-%m-%d"), "minkabu_combined"),
                "ticker": self.ticker,
                "scraped_at": scraped_at,
            }

            found_any = False
            for sub in sub_pages:
                target_url = f"https://minkabu.jp/stock/{self.minkabu_ticker}/{sub}"
                content = await self._get_page_content(page, target_url)
                data_record[sub] = content if content else ""
                if content:
                    found_any = True

            await browser.close()

            results = {}
            if found_any:
                results["minkabu_raw_html"] = HarvesterResult(
                    tags={"ticker": self.ticker, "YEAR": scraped_at.strftime("%Y")}, data=[data_record]
                )
            return results
