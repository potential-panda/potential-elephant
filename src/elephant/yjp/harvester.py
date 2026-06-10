import asyncio
import hashlib
import os
import random
import re
from datetime import datetime
from typing import Optional

import pandas as pd
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from elephant.framework import Harvester, HarvesterResult, Store
from elephant.ticker_registry import update_speed

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15",
]


def generate_id(*args):
    content = "|".join(str(arg) for arg in args)
    return hashlib.md5(content.encode()).hexdigest()


class YahooFinanceHarvester(Harvester):
    def __init__(self, store: Store, ticker: str, tickers_file: Optional[str] = None):
        super().__init__(store)
        from elephant.ticker_registry import normalize_ticker, is_jp_ticker
        ticker = normalize_ticker(ticker)
        if not is_jp_ticker(ticker):
            raise ValueError(
                f"YahooFinanceHarvester only supports JP (.T) tickers — got {ticker!r}. "
                "US tickers have no Yahoo Finance Japan BBS page."
            )
        self.ticker = ticker
        self.tickers_file = tickers_file
        self.latest_ids = self._load_latest_ids()

    def _load_latest_ids(self) -> int:
        """Return the maximum post_id already stored for this ticker, or 0 if none."""
        path_pattern = os.path.join(
            self.store.root_dir, "dataset=yahoo_comments", f"ticker={self.ticker}", "**", "data.parquet"
        )
        import glob

        files = glob.glob(path_pattern, recursive=True)
        if not files:
            return 0

        try:
            dfs = [pd.read_parquet(f, columns=["post_id"]) for f in files]
            df = pd.concat(dfs, ignore_index=True)
            if "post_id" in df.columns:
                return int(df["post_id"].astype(int).max())
        except Exception:
            pass
        return 0

    def get_url(self, params: dict) -> str:
        return f"https://finance.yahoo.co.jp/quote/{self.ticker}/forum"

    async def _get_page_content(self, page, url: str) -> bool:
        """Navigates to the URL with randomized jitter and stealth."""
        wait_time = random.uniform(3, 8)
        print(f"Waiting {wait_time:.2f} seconds before loading {url}...")
        await asyncio.sleep(wait_time)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Use class*= attribute selectors — stable across CSS module hash changes
            await page.wait_for_selector(
                "[class*='_EvaluationGraph__graph_'], [class*='_InfiniteBbsList__item_']",
                timeout=30000,
            )
            return True
        except Exception as e:
            print(f"Error loading {url}: {e}")
            return False

    def _extract_post_id(self, href: str) -> Optional[str]:
        if not href:
            return None
        match = re.search(r"/forum/(\d+)", href)
        return match.group(1) if match else None

    def _extract_user_id(self, href: str) -> Optional[str]:
        if not href:
            return None
        match = re.search(r"user=([^&]+)", href)
        return match.group(1) if match else None

    async def scrape(self, url: str, params: dict) -> dict[str, HarvesterResult]:
        max_pages = params.get("max_pages", 10)
        max_comments = params.get("max_comments", 200)
        user_agent = random.choice(USER_AGENTS)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            evaluation_data = {}
            all_comments = []
            stop_scrolling = False

            if await self._get_page_content(page, url):
                # Extract Evaluation — use class*= to survive CSS module hash changes
                eval_container = await page.query_selector("[class*='_EvaluationGraph__graph_']")
                if eval_container:
                    spans = await eval_container.query_selector_all("span")
                    for span in spans:
                        cls = await span.get_attribute("class")
                        style = await span.get_attribute("style")
                        width_match = re.search(r"width:([\d.]+)%", style or "")
                        rate = float(width_match.group(1)) if width_match else 0.0
                        eval_type = None
                        for t in ["strongest", "strong", "both", "weak", "weakest"]:
                            if f"--{t}" in (cls or ""):
                                eval_type = t
                                break
                        if eval_type:
                            evaluation_data[eval_type] = rate

                evaluation_data["ticker"] = self.ticker
                scraped_at = datetime.now()
                evaluation_data["scraped_at"] = scraped_at
                evaluation_data["id"] = generate_id(self.ticker, scraped_at.strftime("%Y-%m-%d"))

                # Extract Comments
                current_page = 1
                while current_page <= max_pages and len(all_comments) < max_comments and not stop_scrolling:
                    comment_elements = await page.query_selector_all("[class*='_InfiniteBbsList__item_']:not([class*='--infeed'])")
                    existing_ids = {c["post_id"] for c in all_comments}

                    new_found = 0
                    for el in comment_elements:
                        if len(all_comments) >= max_comments:
                            break
                        post_id_el = await el.query_selector("a[href*='/forum/'][class*='_BbsItem__commentNo_']")
                        post_id = self._extract_post_id(await post_id_el.get_attribute("href")) if post_id_el else None

                        if post_id:
                            # Early exit if we hit a previously scraped comment
                            if self.latest_ids > 0 and int(post_id) <= self.latest_ids:
                                print(f"[{self.ticker}] Found previously scraped comment (ID: {post_id} <= max stored {self.latest_ids}). Stopping.")
                                stop_scrolling = True
                                break

                            if post_id not in existing_ids:
                                time_el = await el.query_selector("time[class*='_BbsItem__postDate_']")
                                post_datetime_str = await time_el.inner_text() if time_el else None
                                author_el = await el.query_selector("a[href*='?user='][class*='_BbsItem__userName_']")
                                author = (
                                    self._extract_user_id(await author_el.get_attribute("href")) if author_el else None
                                )
                                body_el = await el.query_selector("div[class*='_BbsItem__body_']")
                                body = await body_el.inner_text() if body_el else None

                                all_comments.append(
                                    {
                                        "id": generate_id(self.ticker, post_id, author, post_datetime_str),
                                        "ticker": self.ticker,
                                        "post_id": post_id,
                                        "post_datetime": post_datetime_str,
                                        "author": author,
                                        "body": body,
                                        "scraped_at": datetime.now(),
                                    }
                                )
                                new_found += 1

                    print(f"[{self.ticker}] Extracted {new_found} new comments (Total: {len(all_comments)})")

                    if stop_scrolling:
                        break

                    bbs_item_selector = "document.querySelectorAll('[class*=\"_InfiniteBbsList__item_\"]')"
                    current_page += 1
                    if current_page <= max_pages and len(all_comments) < max_comments:
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(random.uniform(3, 8))
                        try:
                            current_count = len(comment_elements)
                            await page.wait_for_function(
                                f"{bbs_item_selector}.length > {current_count}",
                                timeout=10000,
                            )
                        except Exception:
                            break
            await browser.close()

            results = {}
            if evaluation_data:
                results["yahoo_evaluations"] = HarvesterResult(
                    tags={"ticker": self.ticker, "date": scraped_at.strftime("%Y")}, data=[evaluation_data]
                )
            if all_comments:
                results["yahoo_comments"] = HarvesterResult(
                    tags={"ticker": self.ticker, "date": scraped_at.strftime("%Y-%m-%d")}, data=all_comments
                )
                if self.tickers_file:
                    try:
                        update_speed(self.tickers_file, self.ticker, len(all_comments), scraped_at)
                    except Exception:
                        pass
            return results
