import asyncio
import random
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15",
]


class YahooFinanceHarvester:
    def __init__(self, ticker: str):
        self.ticker = ticker
        if not ticker.endswith(".T"):
            self.ticker = f"{ticker}.T"
        self.base_url = f"https://finance.yahoo.co.jp/quote/{self.ticker}/forum"
        self.user_agent = random.choice(USER_AGENTS)

    async def _get_page_content(self, page, url: str) -> bool:
        """Navigates to the URL with randomized jitter and stealth."""
        wait_time = random.uniform(3, 8)
        print(f"Waiting {wait_time:.2f} seconds before loading {url}...")
        await asyncio.sleep(wait_time)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Wait for either evaluation or comments to appear
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

    async def scrape(self, max_pages: int = 5, max_comments: int = 100) -> Tuple[Dict, List[Dict]]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=self.user_agent)
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            evaluation_data = {}
            all_comments = []

            if await self._get_page_content(page, self.base_url):
                eval_container = await page.query_selector("._EvaluationGraph__graph_xyp4h_72")
                if eval_container:
                    spans = await eval_container.query_selector_all("span")
                    for span in spans:
                        style = await span.get_attribute("style")
                        cls = await span.get_attribute("class")
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
                evaluation_data["scraped_at"] = datetime.now()

                current_page = 1
                while current_page <= max_pages and len(all_comments) < max_comments:
                    comment_elements = await page.query_selector_all("li._InfiniteBbsList__item_1aetx_12")
                    
                    # Extract comments from the currently loaded set
                    # We use a set of post_ids to avoid duplicates during scrolling
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
                                    "ticker": self.ticker,
                                    "post_id": post_id,
                                    "post_datetime": post_datetime_str,
                                    "author": author,
                                    "body": body,
                                    "scraped_at": datetime.now(),
                                }
                            )
                            new_found += 1
                    
                    print(f"Extracted {new_found} new comments (Total: {len(all_comments)})")

                    current_page += 1
                    if current_page <= max_pages and len(all_comments) < max_comments:
                        # Scroll to bottom to trigger AJAX
                        print(f"Scrolling for more comments (Target Page {current_page})...")
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        
                        # Randomized jitter after scroll
                        wait_time = random.uniform(3, 8)
                        await asyncio.sleep(wait_time)
                        
                        # Wait for more elements to load or a short timeout
                        try:
                            # We check if the number of li elements increases
                            current_count = len(comment_elements)
                            await page.wait_for_function(
                                f"document.querySelectorAll('li._InfiniteBbsList__item_1aetx_12').length > {current_count}",
                                timeout=10000
                            )
                        except Exception:
                            print("No more comments loaded or timeout reached.")
                            break
            await browser.close()
            return evaluation_data, all_comments
