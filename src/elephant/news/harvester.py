import asyncio
import calendar
import hashlib
import logging
from datetime import datetime, timedelta, timezone

import feedparser

from elephant.framework import Harvester, HarvesterResult, Store

# Curated set of feeds covering JP market news and US macro context.
# feedparser handles encoding and date quirks across formats.
RSS_FEEDS = [
    # Google News RSS — topic-scoped, broad coverage
    # (Reuters public RSS feeds were discontinued)
    {
        "source": "gnews_jp_economy",
        "url": "https://news.google.com/rss/search?q=japan+economy+stock+market&hl=en&gl=JP&ceid=JP:en",
        "lang": "en",
    },
    {
        "source": "gnews_semiconductor",
        "url": "https://news.google.com/rss/search?q=semiconductor+chip+japan&hl=en&gl=JP&ceid=JP:en",
        "lang": "en",
    },
    {
        "source": "gnews_ai_infra",
        "url": "https://news.google.com/rss/search?q=AI+infrastructure+investment+data+center&hl=en&gl=US&ceid=US:en",
        "lang": "en",
    },
    {
        "source": "gnews_robotics",
        "url": "https://news.google.com/rss/search?q=robotics+humanoid+automation+japan&hl=en&gl=JP&ceid=JP:en",
        "lang": "en",
    },
    {
        "source": "gnews_biotech_jp",
        "url": "https://news.google.com/rss/search?q=japan+pharma+biotech+longevity&hl=en&gl=JP&ceid=JP:en",
        "lang": "en",
    },
    {
        "source": "gnews_power_grid",
        "url": "https://news.google.com/rss/search?q=power+grid+nuclear+data+center+energy&hl=en&gl=US&ceid=US:en",
        "lang": "en",
    },
]

MAX_ITEMS_PER_FEED = 20
NEWS_DAYS = 5  # ignore articles older than this

# HTML pages (no RSS) — scraped via playwright.
# kind: "minkabu" uses #news_list selector; "yahoo_finance_jp" uses /news/detail/ links.
HTML_NEWS_SOURCES = [
    {
        "source": "minkabu_jp_news",
        "url": "https://minkabu.jp/news",
        "lang": "ja",
        "base_url": "https://minkabu.jp",
        "kind": "minkabu",
    },
    {
        "source": "minkabu_us_news",
        "url": "https://us.minkabu.jp/news",
        "lang": "ja",
        "base_url": "https://us.minkabu.jp",
        "kind": "minkabu",
    },
    {
        "source": "yahoo_finance_jp_us_stocks",
        "url": "https://finance.yahoo.co.jp/news/search/?q=%E7%B1%B3%E5%9B%BD%E6%A0%AA&queryType=andQuery&category=all",
        "lang": "ja",
        "base_url": "",
        "kind": "yahoo_finance_jp",
    },
]


def _generate_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


class NewsHarvester(Harvester):
    def __init__(self, store: Store):
        super().__init__(store)

    def get_url(self, params: dict) -> str:
        return "rss://multiple"

    async def _scrape_html_sources(self, all_items: list, scraped_at: datetime) -> None:
        from playwright.async_api import async_playwright
        from playwright_stealth import Stealth

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            for cfg in HTML_NEWS_SOURCES:
                try:
                    await page.goto(cfg["url"], wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(2000)

                    if cfg["kind"] == "minkabu":
                        raw = await page.evaluate("""() => {
                            const results = [];
                            document.querySelectorAll('.title_box a, li a[href*="/news/"]').forEach(a => {
                                const title = a.textContent.trim();
                                const href = a.getAttribute('href');
                                if (title && href && /\\/news\\/\\d+/.test(href))
                                    results.push({title, href});
                            });
                            return results;
                        }""")
                        for item in raw[:MAX_ITEMS_PER_FEED]:
                            href = item["href"]
                            url = href if href.startswith("http") else cfg["base_url"] + href
                            all_items.append({
                                "id": _generate_id(url),
                                "source": cfg["source"],
                                "lang": cfg["lang"],
                                "title": item["title"],
                                "summary": "",
                                "url": url,
                                "published": "",
                                "scraped_at": scraped_at,
                            })

                    elif cfg["kind"] == "yahoo_finance_jp":
                        raw = await page.evaluate("""() => {
                            const results = [];
                            document.querySelectorAll('a[href*="/news/detail/"]').forEach(a => {
                                const titleEl = a.querySelector('[class*="title"]');
                                const title = titleEl ? titleEl.textContent.trim() : '';
                                const href = a.href;
                                if (title && href) results.push({title, href});
                            });
                            return results;
                        }""")
                        for item in raw[:MAX_ITEMS_PER_FEED]:
                            all_items.append({
                                "id": _generate_id(item["href"]),
                                "source": cfg["source"],
                                "lang": cfg["lang"],
                                "title": item["title"],
                                "summary": "",
                                "url": item["href"],
                                "published": "",
                                "scraped_at": scraped_at,
                            })

                    logging.info(f"[News] {cfg['source']}: scraped HTML page")
                except Exception:
                    logging.exception(f"[News] Failed to scrape HTML source {cfg['source']}")

            await browser.close()

    async def scrape(self, url: str, params: dict) -> dict[str, HarvesterResult]:
        scraped_at = datetime.now()
        date_str = scraped_at.strftime("%Y-%m-%d")
        all_items = []

        for feed_config in RSS_FEEDS:
            try:
                # feedparser is synchronous — offload to thread to avoid blocking the loop
                feed = await asyncio.to_thread(feedparser.parse, feed_config["url"])
                cutoff = datetime.now(tz=timezone.utc) - timedelta(days=NEWS_DAYS)
                for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
                    title = (entry.get("title") or "").strip()
                    link = (entry.get("link") or "").strip()
                    summary = (entry.get("summary") or entry.get("description") or "").strip()
                    published = str(entry.get("published") or entry.get("updated") or "")

                    if not title or not link:
                        continue

                    pub_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
                    if pub_parsed:
                        pub_dt = datetime.fromtimestamp(calendar.timegm(pub_parsed), tz=timezone.utc)
                        if pub_dt < cutoff:
                            continue

                    all_items.append(
                        {
                            "id": _generate_id(link),
                            "source": feed_config["source"],
                            "lang": feed_config["lang"],
                            "title": title,
                            "summary": summary[:500],
                            "url": link,
                            "published": published,
                            "scraped_at": scraped_at,
                        }
                    )
                logging.info(f"[News] {feed_config['source']}: {len(feed.entries)} items")
            except Exception:
                logging.exception(f"[News] Failed to fetch {feed_config['source']}")

        await self._scrape_html_sources(all_items, scraped_at)

        results = {}
        if all_items:
            results["news_headlines"] = HarvesterResult(
                tags={"date": date_str},
                data=all_items,
            )
        return results
