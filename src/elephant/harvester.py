import asyncio
import hashlib
import os
import random
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from elephant.framework import Harvester, HarvesterResult, HarvesterTask, Planner

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
    def get_url(self, params: dict) -> str:
        ticker = params["ticker"]
        if not ticker.endswith(".T"):
            ticker = f"{ticker}.T"
        return f"https://finance.yahoo.co.jp/quote/{ticker}/forum"

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
        ticker = params.get("ticker")
        if not ticker.endswith(".T"):
            ticker = f"{ticker}.T"

        max_pages = params.get("max_pages", 5)
        max_comments = params.get("max_comments", 100)
        user_agent = random.choice(USER_AGENTS)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            evaluation_data = {}
            all_comments = []

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

                evaluation_data["ticker"] = ticker
                scraped_at = datetime.now()
                evaluation_data["scraped_at"] = scraped_at
                evaluation_data["id"] = generate_id(ticker, scraped_at.strftime("%Y-%m-%d"))

                # Extract Comments
                current_page = 1
                while current_page <= max_pages and len(all_comments) < max_comments:
                    comment_elements = await page.query_selector_all("li._InfiniteBbsList__item_1aetx_12")
                    existing_ids = {c["post_id"] for c in all_comments}
                    
                    new_found = 0
                    for el in comment_elements:
                        if len(all_comments) >= max_comments:
                            break
                        post_id_el = await el.query_selector("a._BbsItem__commentNo_qgr82_41")
                        post_id = self._extract_post_id(await post_id_el.get_attribute("href")) if post_id_el else None
                        
                        if post_id and post_id not in existing_ids:
                            time_el = await el.query_selector("time._BbsItem__postDate_qgr82_37")
                            post_datetime_str = await time_el.inner_text() if time_el else None
                            author_el = await el.query_selector("a._BbsItem__userName_qgr82_34")
                            author = self._extract_user_id(await author_el.get_attribute("href")) if author_el else None
                            body_el = await el.query_selector("div._BbsItem__body_qgr82_84")
                            body = await body_el.inner_text() if body_el else None
                            
                            all_comments.append(
                                {
                                    "id": generate_id(ticker, post_id, author, post_datetime_str),
                                    "ticker": ticker,
                                    "post_id": post_id,
                                    "post_datetime": post_datetime_str,
                                    "author": author,
                                    "body": body,
                                    "scraped_at": datetime.now(),
                                }
                            )
                            new_found += 1
                    
                    print(f"[{ticker}] Extracted {new_found} new comments (Total: {len(all_comments)})")

                    current_page += 1
                    if current_page <= max_pages and len(all_comments) < max_comments:
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(random.uniform(3, 8))
                        try:
                            current_count = len(comment_elements)
                            await page.wait_for_function(
                                f"document.querySelectorAll('li._InfiniteBbsList__item_1aetx_12').length > {current_count}",
                                timeout=10000
                            )
                        except Exception:
                            break
            await browser.close()
            
            results = {}
            if evaluation_data:
                results["yahoo_evaluations"] = HarvesterResult(
                    tags={"ticker": ticker, "date": scraped_at.strftime("%Y")},
                    data=[evaluation_data]
                )
            if all_comments:
                results["yahoo_comments"] = HarvesterResult(
                    tags={"ticker": ticker, "date": scraped_at.strftime("%Y-%m-%d")},
                    data=all_comments
                )
            return results


class YahooFinancePlanner(Planner):
    def __init__(self, harvester: Harvester, tickers_file: str):
        self.harvester = harvester
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

        random.shuffle(tickers)
        tasks = []
        
        # Time range: 10:17 to 12:23
        start_min = 10 * 60 + 17
        end_min = 12 * 60 + 23
        
        today = datetime.now()
        
        for ticker in tickers:
            random_min = random.randint(start_min, end_min)
            scheduled_at = today.replace(
                hour=random_min // 60, 
                minute=random_min % 60, 
                second=0, 
                microsecond=0
            )
            tasks.append(
                HarvesterTask(
                    harvester=self.harvester,
                    scheduled_at=scheduled_at,
                    args={"ticker": ticker, "max_pages": 10, "max_comments": 200}
                )
            )
        
        return tasks
