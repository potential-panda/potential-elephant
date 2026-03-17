import asyncio
import hashlib
import os
import random
import re
from datetime import datetime
from typing import Dict, List, Optional

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from elephant.framework import Harvester, HarvesterResult, Store


def generate_id(*args):
    content = "|".join(str(arg) for arg in args)
    return hashlib.md5(content.encode()).hexdigest()


class MinkabuHarvester(Harvester):
    def __init__(self, store: Store, ticker: str):
        super().__init__(store)
        # Minkabu doesn't use the .T suffix in its URL structure
        self.ticker = ticker.replace(".T", "")
        # We'll store both the Minkabu ID and the normalized ticker
        self.normalized_ticker = f"{self.ticker}.T"

    def get_url(self, params: dict) -> str:
        # Target the main stock page
        return f"https://minkabu.jp/stock/{self.ticker}"

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

    async def _get_page_content(self, page, url: str) -> bool:
        wait_time = random.uniform(3, 8)
        print(f"Waiting {wait_time:.2f} seconds before loading {url}...")
        await asyncio.sleep(wait_time)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Wait for a broad container that usually holds stock data
            await page.wait_for_selector(".stock_price_area, #content", timeout=30000)
            return True
        except Exception as e:
            print(f"Error loading {url}: {e}")
            return False

    async def scrape(self, url: str, params: dict) -> dict[str, HarvesterResult]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            minkabu_data = []
            scraped_at = datetime.now()

            if await self._get_page_content(page, url):
                # Grab a high-level container (The stock detail area)
                # Instead of brittle CSS, we take the main summary block
                container = await page.query_selector(".stock_price_area")
                if not container:
                    container = await page.query_selector("#content")
                
                if container:
                    raw_html = await container.inner_html()
                    cleaned_html = self._clean_html(raw_html)
                    
                    minkabu_data.append({
                        "id": generate_id(self.normalized_ticker, scraped_at.strftime("%Y-%m-%d"), "minkabu_summary"),
                        "ticker": self.normalized_ticker,
                        "raw_html": cleaned_html,
                        "scraped_at": scraped_at
                    })
                else:
                    print(f"[{self.normalized_ticker}] Main container not found on Minkabu.")

            await browser.close()
            
            results = {}
            if minkabu_data:
                results["minkabu_raw_html"] = HarvesterResult(
                    tags={"ticker": self.normalized_ticker, "date": scraped_at.strftime("%Y-%m-%d")},
                    data=minkabu_data
                )
            return results
