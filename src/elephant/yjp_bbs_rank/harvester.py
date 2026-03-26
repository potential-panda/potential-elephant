import asyncio
import random
import re

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from elephant.framework import Harvester, Store

BASE_URL = "https://finance.yahoo.co.jp/stocks/ranking/bbs?market=all&term=daily"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15",
]


class BbsRankHarvester(Harvester):
    def __init__(self, store: Store, tickers_file: str, max_pages: int = 2):
        super().__init__(store)
        self.tickers_file = tickers_file
        self.max_pages = max_pages

    def get_url(self, params: dict) -> str:
        return BASE_URL

    async def _scrape_page(self, page, page_num: int) -> list[str]:
        url = BASE_URL if page_num == 1 else f"{BASE_URL}&page={page_num}"
        wait_time = random.uniform(3, 8)
        print(f"[BbsRank] Waiting {wait_time:.2f}s before loading page {page_num}...")
        await asyncio.sleep(wait_time)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector("table", timeout=30000)
        except Exception as e:
            print(f"[BbsRank] Error loading page {page_num}: {e}")
            return []

        tickers = []
        links = await page.query_selector_all("a[href*='/quote/']")
        for link in links:
            href = await link.get_attribute("href")
            match = re.search(r"/quote/(\d+\.T)/", href or "")
            if match:
                ticker = match.group(1)
                if ticker not in tickers:
                    tickers.append(ticker)

        print(f"[BbsRank] Found {len(tickers)} tickers on page {page_num}")
        return tickers

    async def scrape(self, url: str, params: dict) -> dict:
        user_agent = random.choice(USER_AGENTS)
        all_tickers = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            for page_num in range(1, self.max_pages + 1):
                tickers = await self._scrape_page(page, page_num)
                for t in tickers:
                    if t not in all_tickers:
                        all_tickers.append(t)

            await browser.close()

        if all_tickers:
            with open(self.tickers_file, "w") as f:
                f.write("\n".join(all_tickers) + "\n")
            print(f"[BbsRank] Wrote {len(all_tickers)} tickers to {self.tickers_file}")
        else:
            print("[BbsRank] No tickers found, tickers.txt not updated.")

        return {}
