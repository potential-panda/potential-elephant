import asyncio
import hashlib
import logging
from datetime import datetime

import feedparser

from elephant.framework import Harvester, HarvesterResult, Store

# Curated set of feeds covering JP market news and US macro context.
# feedparser handles encoding and date quirks across formats.
RSS_FEEDS = [
    # NHK Business/Economy — reliable public JP broadcaster
    {"source": "nhk_business", "url": "https://www.nhk.or.jp/rss/news/cat4.xml", "lang": "ja"},
    # Reuters global business and tech — macro and sector context
    {"source": "reuters_business", "url": "https://feeds.reuters.com/reuters/businessNews", "lang": "en"},
    {"source": "reuters_tech", "url": "https://feeds.reuters.com/reuters/technologyNews", "lang": "en"},
    # Google News RSS — topic-scoped, broad coverage
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
]

MAX_ITEMS_PER_FEED = 20


def _generate_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


class NewsHarvester(Harvester):
    def __init__(self, store: Store):
        super().__init__(store)

    def get_url(self, params: dict) -> str:
        return "rss://multiple"

    async def scrape(self, url: str, params: dict) -> dict[str, HarvesterResult]:
        scraped_at = datetime.now()
        date_str = scraped_at.strftime("%Y-%m-%d")
        all_items = []

        for feed_config in RSS_FEEDS:
            try:
                # feedparser is synchronous — offload to thread to avoid blocking the loop
                feed = await asyncio.to_thread(feedparser.parse, feed_config["url"])
                for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
                    title = (entry.get("title") or "").strip()
                    link = (entry.get("link") or "").strip()
                    summary = (entry.get("summary") or entry.get("description") or "").strip()
                    published = str(entry.get("published") or entry.get("updated") or "")

                    if not title or not link:
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

        results = {}
        if all_items:
            results["news_headlines"] = HarvesterResult(
                tags={"date": date_str},
                data=all_items,
            )
        return results
