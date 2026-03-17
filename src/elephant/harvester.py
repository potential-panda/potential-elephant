import asyncio
import hashlib
import os
import random
import re
from datetime import datetime
from typing import List, Optional, Set

import pandas as pd
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from elephant.framework import Harvester, HarvesterResult, HarvesterTask, Planner, Store

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
    def __init__(self, store: Store, ticker: str):
        super().__init__(store)
        if not ticker.endswith(".T"):
            ticker = f"{ticker}.T"
        self.ticker = ticker
        self.latest_ids = self._load_latest_ids()

    def _load_latest_ids(self, count=5) -> Set[str]:
        """Retrieve the latest N post IDs from the store for this ticker."""
        path_pattern = os.path.join(
            self.store.root_dir, "dataset=yahoo_comments", f"ticker={self.ticker}", "**", "data.parquet"
        )
        import glob
        files = glob.glob(path_pattern, recursive=True)
        if not files:
            return set()
        
        try:
            dfs = [pd.read_parquet(f) for f in files]
            df = pd.concat(dfs, ignore_index=True)
            if "post_datetime" in df.columns and "post_id" in df.columns:
                df["post_datetime_dt"] = pd.to_datetime(df["post_datetime"])
                latest_ids = df.sort_values(by="post_datetime_dt", ascending=False).head(count)["post_id"].tolist()
                return set(latest_ids)
        except Exception:
            # We can log here if needed, but for now just return empty set
            pass
        return set()

    def get_url(self, params: dict) -> str:
        return f"https://finance.yahoo.co.jp/quote/{self.ticker}/forum"

    async def _get_page_content(self, page, url: str) -> bool:
        """Navigates to the URL with randomized jitter and stealth."""
        wait_time = random.uniform(3, 8)
        print(f"Waiting {wait_time:.2f} seconds before loading {url}...")
        await asyncio.sleep(wait_time)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(
                "._EvaluationGraph__graph_xyp4h_72, ._InfiniteBbsList__item_1aetx_12", timeout=30000
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
                # Extract Evaluation
                eval_container = await page.query_selector("._EvaluationGraph__graph_xyp4h_72")
                if eval_container:
                    spans = await eval_container.query_selector_all("span")
                    for span in spans:
                        cls = await span.get_attribute("class")
                        style = await span.get_attribute("style")
                        width_match = re.search(r"width:([\d.]+)%", style or "")
                        rate = float(width_match.group(1)) if width_match else 0.0
                        eval_type = None
                        for t in ["strongest", "strong", "both", "weak", "weakest"]:
                            if f"--{t}_" in (cls or ""):
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
                    comment_elements = await page.query_selector_all("li._InfiniteBbsList__item_1aetx_12")
                    existing_ids = {c["post_id"] for c in all_comments}
                    
                    new_found = 0
                    for el in comment_elements:
                        if len(all_comments) >= max_comments:
                            break
                        post_id_el = await el.query_selector("a._BbsItem__commentNo_qgr82_41")
                        post_id = self._extract_post_id(await post_id_el.get_attribute("href")) if post_id_el else None
                        
                        if post_id:
                            # Early exit if we hit a previously scraped comment
                            if post_id in self.latest_ids:
                                print(f"[{self.ticker}] Found previously scraped comment (ID: {post_id}). Stopping.")
                                stop_scrolling = True
                                break

                            if post_id not in existing_ids:
                                time_el = await el.query_selector("time._BbsItem__postDate_qgr82_37")
                                post_datetime_str = await time_el.inner_text() if time_el else None
                                author_el = await el.query_selector("a._BbsItem__userName_qgr82_34")
                                author = (
                                    self._extract_user_id(await author_el.get_attribute("href")) if author_el else None
                                )
                                body_el = await el.query_selector("div._BbsItem__body_qgr82_84")
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

                    bbs_item_selector = "document.querySelectorAll('li._InfiniteBbsList__item_1aetx_12')"
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
            return results


class YahooFinancePlanner(Planner):
    def __init__(self, store: Store, tickers_file: str):
        self.store = store
        self.tickers_file = tickers_file

    def _get_tickers(self) -> List[str]:
        if not os.path.exists(self.tickers_file):
            return []
        with open(self.tickers_file, "r") as f:
            return [line.strip() for line in f if line.strip()]

    def create(self) -> List[HarvesterTask]:
        tickers = self._get_tickers()
        if not tickers:
            return []

        tasks = []
        
        # Time range: 10:17 (617 mins) to 23:23 (1403 mins)
        start_min = 617
        end_min = 1423 
        
        available_minutes = list(range(start_min, end_min + 1))
        random.shuffle(available_minutes)
        
        today = datetime.now()
        
        for i, ticker in enumerate(tickers):
            random_min = available_minutes[i % len(available_minutes)]
            scheduled_at = today.replace(hour=random_min // 60, minute=random_min % 60, second=0, microsecond=0)
            
            # Create a NEW harvester instance for EACH ticker
            harvester = YahooFinanceHarvester(self.store, ticker)
            
            tasks.append(
                HarvesterTask(
                    harvester=harvester,
                    scheduled_at=scheduled_at,
                    args={"max_pages": 10, "max_comments": 200},
                )
            )
        
        random.shuffle(tasks)
        return tasks
