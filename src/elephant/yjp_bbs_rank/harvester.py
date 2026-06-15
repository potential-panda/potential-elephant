import asyncio
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from elephant.framework import Harvester, Store
from elephant.ticker_registry import load_cache, save_cache

BASE_URL = "https://finance.yahoo.co.jp/stocks/ranking/bbs?market=all&term=daily"

CACHE_TTL_DAYS = 28
CACHE_MAX_TICKERS = 300

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
            self._update_cache(all_tickers)
        else:
            print("[BbsRank] No tickers found, tickers.txt not updated.")

        return {}

    def _update_cache(self, today_tickers: list[str]) -> None:
        today = datetime.now().date()
        cutoff = today - timedelta(days=CACHE_TTL_DAYS)
        today_str = today.isoformat()
        cutoff_str = cutoff.isoformat()

        cache = load_cache(self.tickers_file)

        # Build 1-indexed rank map for today's tickers
        bbs_rank = {ticker: i for i, ticker in enumerate(today_tickers, 1)}

        # Refresh last_seen for today's ranked tickers and update rank in speed_history
        for ticker in today_tickers:
            entry = cache.get(ticker) or {"speed_history": []}
            entry["last_seen"] = today_str
            # Update today's speed_history entry with the rank
            history = entry.get("speed_history", [])
            today_entry = next((h for h in history if h.get("date") == today_str), None)
            if today_entry is not None:
                today_entry["rank"] = bbs_rank[ticker]
            cache[ticker] = entry

        # Evict entries older than TTL (compare last_seen date)
        def _last_seen(entry) -> str:
            if isinstance(entry, str):
                return entry
            return entry.get("last_seen", "")

        cache = {t: e for t, e in cache.items() if _last_seen(e) >= cutoff_str}

        # Prune speed_history entries older than TTL
        for ticker, entry in cache.items():
            if isinstance(entry, dict) and "speed_history" in entry:
                entry["speed_history"] = [
                    h for h in entry["speed_history"] if h.get("date", "") >= cutoff_str
                ]

        # Cap at max: keep most recently seen, preserving today's rank order first
        if len(cache) > CACHE_MAX_TICKERS:
            sorted_entries = sorted(
                cache.items(),
                key=lambda x: (_last_seen(x[1]), today_tickers.index(x[0]) if x[0] in today_tickers else 999),
                reverse=True,
            )
            cache = dict(sorted_entries[:CACHE_MAX_TICKERS])

        save_cache(self.tickers_file, cache)

        # Write tickers.txt: today's ranked tickers first, then retained cache tickers
        retained = [t for t in cache if t not in today_tickers]
        final_list = today_tickers + retained

        with open(self.tickers_file, "w") as f:
            f.write("\n".join(final_list) + "\n")

        print(f"[BbsRank] {len(today_tickers)} tickers today + {len(retained)} retained = {len(final_list)} total in tickers.txt")
