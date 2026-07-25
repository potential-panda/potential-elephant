import asyncio
import calendar
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

import feedparser

from elephant.config import SOURCE_REGISTRY_FILE, TICKERS_FILE
from elephant.framework import Harvester, HarvesterResult, Store
from elephant.source.fool_urls import fool_quote_urls
from elephant.web_client import open_web_page, visit_page
from elephant.source_registry import SourceRegistry
from elephant.ticker_registry import load_us_tickers, normalize_ticker

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
FOOL_MAX_TICKERS = 50
FOOL_DATE_RE = re.compile(r"[A-Z][a-z]{2} \d{1,2}, \d{4}")

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


def _include_general_news(params: dict) -> bool:
    """General/newswire feeds are disabled by default.

    They are useful for finding new tickers, but the current pipeline is scoped
    to known tickers and resolved ticker-source URLs.
    """
    return bool(params.get("include_general_news"))


def _generate_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _load_fool_tickers(params: dict, tickers_file: str = TICKERS_FILE) -> list[str]:
    configured = params.get("fool_tickers")
    if isinstance(configured, str):
        candidates = [configured]
    elif configured:
        candidates = list(configured)
    else:
        candidates = list(load_us_tickers(tickers_file).keys())

    result = []
    seen = set()
    for raw in candidates:
        ticker = normalize_ticker(str(raw).strip().upper())
        if not ticker or ticker.endswith(".T") or ticker in seen:
            continue
        seen.add(ticker)
        result.append(ticker)
    return result[: int(params.get("fool_max_tickers", FOOL_MAX_TICKERS))]


def _load_fool_sources(params: dict, registry_file: str = SOURCE_REGISTRY_FILE) -> list[tuple[str, str]]:
    configured = params.get("fool_sources")
    if configured:
        rows = []
        for item in configured:
            ticker = normalize_ticker(str(item.get("ticker", "")).strip().upper())
            url = str(item.get("url", "")).strip()
            if ticker and url:
                rows.append((ticker, url))
        return rows

    registry = SourceRegistry(registry_file)
    rows = [(ticker, source["urls"][0]) for ticker, source_id, source in registry.available_sources("fool_quote_news")]
    if rows:
        return rows[: int(params.get("fool_max_tickers", FOOL_MAX_TICKERS))]

    if "fool_tickers" not in params:
        return []

    # Developer/testing override. Normal scheduled harvesting should rely on
    # SourceRegistry URLs populated by SourceAvailabilityCheck.
    return [(ticker, url) for ticker in _load_fool_tickers(params) for url in _fool_quote_urls(ticker)[:1]]


def _fool_quote_urls(ticker: str) -> list[str]:
    return fool_quote_urls(ticker)[1]


def _parse_fool_card(raw: dict, ticker: str, quote_url: str, scraped_at: datetime) -> dict | None:
    title = (raw.get("title") or "").strip()
    url = (raw.get("href") or "").strip()
    if not title or not url:
        return None

    card_text = (raw.get("card") or "").strip()
    tail = card_text.replace(title, "", 1).strip() if card_text.startswith(title) else card_text
    date_match = FOOL_DATE_RE.search(tail)
    published = date_match.group(0) if date_match else ""
    author = tail[: date_match.start()].strip() if date_match else tail

    return {
        "id": _generate_id(url),
        "source": "fool_us_quote_news",
        "lang": "en",
        "ticker": ticker,
        "title": title,
        "summary": "",
        "url": url,
        "published": published,
        "author": author,
        "quote_url": quote_url,
        "scraped_at": scraped_at,
    }


class NewsHarvester(Harvester):
    def __init__(self, store: Store):
        super().__init__(store)

    def get_url(self, params: dict) -> str:
        return "rss://multiple"

    async def _scrape_html_sources(self, all_items: list, scraped_at: datetime) -> None:
        async with open_web_page() as page:

            for cfg in HTML_NEWS_SOURCES:
                try:
                    await visit_page(page, cfg["url"])
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

    async def _scrape_fool_quote_news(self, all_items: list, scraped_at: datetime, params: dict) -> None:
        sources = _load_fool_sources(params)
        if not sources:
            return

        extract_script = """(ticker) => {
            const heading = Array.from(document.querySelectorAll('h2, h3')).find(el =>
                el.textContent.trim().toLowerCase() === `${ticker.toLowerCase()} news`
            );
            if (!heading) return [];
            let root = heading;
            const selector = 'a[href*="/investing/"], a[href*="/coverage/"]';
            while (root && root.querySelectorAll(selector).length === 0) {
                root = root.parentElement;
            }
            if (!root) return [];
            return Array.from(root.querySelectorAll(selector)).map(a => {
                const card = a.closest('article, li') || a.parentElement;
                return {
                    title: a.textContent.trim(),
                    href: a.href,
                    card: card ? card.textContent.trim() : ''
                };
            }).filter(item => item.title.length > 20 && item.href);
        }"""

        async with open_web_page() as page:

            for ticker, quote_url in sources:
                try:
                    await visit_page(page, quote_url)
                    await page.wait_for_timeout(2000)
                    raw_items = await page.evaluate(extract_script, ticker)
                    parsed = [
                        item
                        for item in (
                            _parse_fool_card(raw, ticker, quote_url, scraped_at)
                            for raw in raw_items[:MAX_ITEMS_PER_FEED]
                        )
                        if item
                    ]
                    if parsed:
                        all_items.extend(parsed)
                        logging.info(f"[News] fool_us_quote_news {ticker}: {len(parsed)} items")
                except Exception:
                    logging.exception(f"[News] Failed to scrape Fool quote page {quote_url}")

    async def scrape(self, url: str, params: dict) -> dict[str, HarvesterResult]:
        scraped_at = datetime.now()
        date_str = scraped_at.strftime("%Y-%m-%d")
        all_items = []

        if _include_general_news(params):
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
        await self._scrape_fool_quote_news(all_items, scraped_at, params)

        results = {}
        if all_items:
            results["news_headlines"] = HarvesterResult(
                tags={"date": date_str},
                data=all_items,
            )
        return results
