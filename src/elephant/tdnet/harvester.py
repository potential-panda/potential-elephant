"""
TDnet harvester — Tokyo Stock Exchange timely disclosures.

Fetches the HTML listing pages from release.tdnet.info and stores
disclosures for watched tickers as Parquet.

URL pattern:
  https://www.release.tdnet.info/inbs/I_list_{page:03d}_{YYYYMMDD}.html
  Page 1 = most recent 100 items; subsequent pages go back in time.

Code format: TDnet uses 5-digit codes where the first 4 are the stock
code and the 5th is the market segment (0=Prime, 1=Standard, 2=Growth).
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from elephant.framework import Harvester, HarvesterResult, Store

JST = ZoneInfo("Asia/Tokyo")
BASE_URL = "https://www.release.tdnet.info/inbs"
DOC_BASE = f"{BASE_URL}/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Referer": "https://www.release.tdnet.info/inbs/I_main_00.html",
}
MAX_PAGES = 5


def _code_to_ticker(code: str) -> str:
    """Convert TDnet 5-digit code to ticker (e.g. '21600' → '2160.T')."""
    return code[:4].lstrip("0") and code[:4] + ".T" or code[:4] + ".T"


def _parse_page(html: str, date_str: str) -> list[dict]:
    """Extract disclosure rows from one TDnet listing page."""
    rows = []
    # Each row: <td class="*-L kjTime">HH:MM</td> ... <td class="*-M kjCode">NNNNN</td> ...
    pattern = re.compile(
        r'class="[^"]*kjTime[^"]*"[^>]*>\s*(\d{2}:\d{2})\s*</td>'
        r'.*?class="[^"]*kjCode[^"]*"[^>]*>\s*(\d{5})\s*</td>'
        r'.*?class="[^"]*kjName[^"]*"[^>]*>\s*(.*?)\s*</td>'
        r'.*?class="[^"]*kjTitle[^"]*"[^>]*>.*?href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        time_str, code, company, href, title = m.groups()
        ticker = _code_to_ticker(code)
        company = re.sub(r"\s+", " ", company).strip()
        title = re.sub(r"\s+", " ", title).strip()
        doc_url = href if href.startswith("http") else f"{DOC_BASE}{href}"
        doc_id = hashlib.md5(f"{date_str}|{code}|{href}".encode()).hexdigest()
        rows.append({
            "id": doc_id,
            "date": date_str,
            "time": time_str,
            "code": code,
            "ticker": ticker,
            "company": company,
            "title": title,
            "document_url": doc_url,
        })
    return rows


def _fetch_date(date_str: str, watched: set[str]) -> list[dict]:
    """Fetch all pages for a given date, returning disclosures for watched tickers."""
    all_rows = []
    for page in range(1, MAX_PAGES + 1):
        url = f"{BASE_URL}/I_list_{page:03d}_{date_str}.html"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            rows = _parse_page(resp.text, date_str)
            if not rows:
                break
            if watched:
                rows = [r for r in rows if r["ticker"] in watched]
            all_rows.extend(rows)
            # Stop if fewer than 100 rows on the page (last page)
            total_match = re.search(r"全(\d+)件", resp.text)
            if total_match:
                total = int(total_match.group(1))
                if page * 100 >= total:
                    break
        except Exception:
            logging.exception(f"[TDnet] Failed to fetch {url}")
            break
    return all_rows


class TDnetHarvester(Harvester):
    def __init__(self, store: Store, lookback_days: int = 1):
        super().__init__(store)
        self.lookback_days = lookback_days

    def get_url(self, params: dict) -> str:
        return BASE_URL

    async def scrape(self, url: str, params: dict) -> dict[str, HarvesterResult]:
        today = datetime.now(JST).date()
        results = {}

        for offset in range(self.lookback_days + 1):
            target = today - timedelta(days=offset)
            date_str = target.strftime("%Y%m%d")
            rows = _fetch_date(date_str, watched=set())
            if not rows:
                continue

            # Add scraped_at timestamp
            now = datetime.now()
            for r in rows:
                r["scraped_at"] = now

            iso_date = target.isoformat()
            results[f"tdnet_{iso_date}"] = HarvesterResult(
                tags={"date": iso_date},
                data=rows,
            )
            print(f"[TDnet] {date_str}: {len(rows)} disclosures for watched tickers")

        # Merge all dates into one dataset key
        if not results:
            return {}

        all_rows = []
        for r in results.values():
            all_rows.extend(r.data)

        target_date = today.isoformat()
        return {
            "tdnet_disclosures": HarvesterResult(
                tags={"date": target_date},
                data=all_rows,
            )
        }
