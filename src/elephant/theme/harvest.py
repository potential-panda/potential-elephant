from __future__ import annotations

import html
import asyncio
import re
from datetime import datetime
from html.parser import HTMLParser
from io import StringIO
from urllib.parse import unquote, urljoin
from urllib.request import Request, urlopen

import pandas as pd

from elephant.config import DATA_DIR
from elephant.framework import HarvesterResult, Store
from elephant.theme.catalog import ThemeSourceDefinition, get_theme_source, infer_theme_id, list_theme_sources
from elephant.theme.io import TODAY, row_id
from elephant.ticker_registry import normalize_ticker


JP_STOCK_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
JP_STOCK_LINK_RE = re.compile(r"(?:code=|/stock/|/stock/\?code=)(\d{4})(?!\d)")
US_TICKER_RE = re.compile(r"\b[A-Z][A-Z0-9.-]{0,5}\b")
COMMON_WORDS = {
    "ETF", "ETFS", "AI", "API", "CSV", "HTML", "JPY", "USD", "THE", "AND",
    "FOR", "INC", "CORP", "LTD", "LLC", "NYSE", "NASDAQ", "AMEX",
}
NON_THEME_LABELS = ("ランキング", "プレミアム", "無料", "ログイン", "会員登録")


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            self._href = attrs_dict.get("href") or ""
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            text = " ".join(" ".join(self._text).split())
            self.links.append((self._href, text))
            self._href = None
            self._text = []


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 PotentialElephant/1.0"})
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="ignore")


def _fetch_text_browser(url: str) -> str:
    async def run():
        from elephant.web_client import open_web_page, visit_page

        async with open_web_page() as page:
            response = await visit_page(page, url, wait_until="domcontentloaded", timeout=30000)
            if response and response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
            await page.wait_for_timeout(2500)
            return await page.content()

    return asyncio.run(run())


def _fetch_text_with_browser_fallback(url: str) -> str:
    try:
        return _fetch_text(url)
    except Exception:
        return _fetch_text_browser(url)


def _strip_html(value: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _normalize_weight(value):
    try:
        text = str(value).replace("%", "").replace(",", "").strip()
        return float(text) if text else ""
    except Exception:
        return ""


def _valid_jp_code(value: str) -> bool:
    try:
        code = int(value)
    except Exception:
        return False
    return 1300 <= code <= 9999


def _slug(value: str) -> str:
    text = unquote(value or "").strip().lower()
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^0-9a-zA-Z一-龥ぁ-んァ-ンー]+", "_", text)
    text = text.strip("_")
    return text[:80] or "theme"


def extract_theme_links(text: str, source: ThemeSourceDefinition) -> list[dict]:
    parser = LinkParser()
    parser.feed(text)
    rows = []
    patterns = source.detail_url_patterns or ("theme",)
    base_url = source.base_url or source.url
    by_url: dict[str, list[str]] = {}
    url_order = []
    for href, label in parser.links:
        if not href or not label:
            continue
        if not any(pattern in href for pattern in patterns):
            continue
        url = urljoin(base_url, href)
        key = url.split("#", 1)[0]
        clean_label = label.strip()
        if (
            "list.html" in key
            or clean_label.upper() in {"ENG", "JP", "Ｎ", "N"}
            or any(blocked in clean_label for blocked in NON_THEME_LABELS)
        ):
            continue
        if key == source.url:
            continue
        if key not in by_url:
            by_url[key] = []
            url_order.append(key)
        by_url[key].append(html.unescape(label).strip())

    for key in url_order:
        labels = [
            label for label in by_url[key]
            if label and not re.fullmatch(r"[0-9A-Z]{1,6}", label) and label.upper() not in {"N", "Ｎ"}
        ]
        source_theme_name = max(labels or by_url[key], key=len).strip()
        canonical = infer_theme_id(source_theme_name, key)
        rows.append({
            "id": row_id("theme_source_theme", source.source_id, key),
            "source_id": source.source_id,
            "source_name": source.name,
            "source_theme_id": f"{source.source_id}:{_slug(source_theme_name or key)}",
            "source_theme_name": source_theme_name,
            "canonical_theme_id": canonical,
            "theme_id": canonical or f"raw_{_slug(source_theme_name or key)}",
            "url": key,
            "rank": len(rows) + 1,
            "source_quality": source.source_quality,
            "theme_purity": source.theme_purity,
            "harvested_at": datetime.now().isoformat(timespec="seconds"),
        })
        if source.top_n and len(rows) >= source.top_n:
            break
    return rows


def extract_tickers_from_html(text: str, include_us: bool = False) -> list[str]:
    parser = LinkParser()
    parser.feed(text)
    plain = _strip_html(text)
    tickers = []
    seen = set()
    for href, label in parser.links:
        joined = f"{href} {label}"
        for match in JP_STOCK_LINK_RE.findall(joined):
            if not _valid_jp_code(match):
                continue
            ticker = normalize_ticker(match)
            if ticker not in seen:
                seen.add(ticker)
                tickers.append(ticker)
    if not tickers and "関連銘柄" in plain:
        # Test and fallback path for pages that expose a compact related-stock
        # block without stock-code links.
        related = plain.split("関連銘柄", 1)[1][:2000]
        candidates = JP_STOCK_RE.findall(related)
    else:
        candidates = []
    for match in candidates:
        if not _valid_jp_code(match):
            continue
        ticker = normalize_ticker(match)
        if ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    if include_us:
        for match in US_TICKER_RE.findall(plain):
            ticker = match.strip().upper().replace(".", "-")
            if ticker in COMMON_WORDS or ticker.isdigit() or len(ticker) < 2:
                continue
            if ticker not in seen:
                seen.add(ticker)
                tickers.append(ticker)
    return tickers


def _theme_member_rows(source: ThemeSourceDefinition, tickers: list[str], theme_row: dict | None = None) -> list[dict]:
    harvested_at = datetime.now().isoformat(timespec="seconds")
    theme_id = (theme_row or {}).get("theme_id") or source.theme_id
    source_theme_id = (theme_row or {}).get("source_theme_id") or source.source_id
    source_theme_name = (theme_row or {}).get("source_theme_name") or source.name
    source_url = (theme_row or {}).get("url") or source.url
    theme_purity = (theme_row or {}).get("theme_purity") or source.theme_purity
    rows = []
    for rank, ticker in enumerate(tickers, 1):
        rows.append({
            "id": row_id("theme_member", source.source_id, source_theme_id, ticker),
            "theme_id": theme_id,
            "ticker": ticker,
            "name": "",
            "source": source.source_id,
            "source_theme_id": source_theme_id,
            "source_theme_name": source_theme_name,
            "source_url": source_url,
            "raw_rank": rank,
            "source_weight": source.source_quality,
            "theme_purity": theme_purity,
            "harvested_at": harvested_at,
        })
    return rows


def _etf_rows_from_frame(source: ThemeSourceDefinition, df: pd.DataFrame) -> list[dict]:
    if source.ticker_column not in df.columns:
        candidates = [c for c in ["ticker", "Ticker", "symbol", "Symbol", "ティッカー", "銘柄コード"] if c in df.columns]
        if not candidates:
            raise ValueError(f"{source.source_id} CSV missing ticker column: {source.ticker_column}")
        ticker_col = candidates[0]
    else:
        ticker_col = source.ticker_column

    weight_col = source.weight_column if source.weight_column in df.columns else None
    if weight_col is None:
        weight_col = next((c for c in ["weight", "Weight", "holding_weight", "% Weight"] if c in df.columns), None)
    name_col = next((c for c in ["name", "Name", "company", "Company", "銘柄名"] if c in df.columns), None)
    as_of = datetime.now().strftime("%Y-%m-%d")
    rows = []
    for _, raw in df.iterrows():
        ticker = normalize_ticker(str(raw.get(ticker_col, "")).strip().upper())
        if not ticker or ticker.lower() == "nan":
            continue
        rows.append({
            "id": row_id("etf_holding", source.source_id, source.etf, source.theme_id, ticker),
            "etf": source.etf or source.source_id,
            "theme_id": source.theme_id,
            "ticker": ticker,
            "name": str(raw.get(name_col, "") if name_col else ""),
            "holding_weight": _normalize_weight(raw.get(weight_col, "")) if weight_col else "",
            "issuer": source.issuer,
            "source_url": source.url,
            "as_of": as_of,
            "theme_purity": source.theme_purity,
            "issuer_quality": source.issuer_quality,
            "harvested_at": datetime.now().isoformat(timespec="seconds"),
        })
    return rows


def harvest_theme_source(source: ThemeSourceDefinition, data_dir: str = DATA_DIR) -> tuple[str, int]:
    if not source.url:
        return ("skipped", 0)
    text = _fetch_text_with_browser_fallback(source.url)
    store = Store(data_dir)
    if source.kind == "theme_index":
        theme_rows = extract_theme_links(text, source)
        if source.source_id == "globalx_jp_fund_list" and not theme_rows:
            text = _fetch_text_browser(source.url)
            theme_rows = extract_theme_links(text, source)
        member_rows = []
        for theme_row in theme_rows:
            try:
                detail_text = _fetch_text_with_browser_fallback(theme_row["url"])
            except Exception:
                continue
            tickers = extract_tickers_from_html(detail_text, include_us=source.source_id.startswith("stocktitan"))
            member_rows.extend(_theme_member_rows(source, tickers, theme_row))
        store.save("theme_source_themes", HarvesterResult(tags={"date": TODAY}, data=theme_rows))
        store.save("theme_members", HarvesterResult(tags={"date": TODAY}, data=member_rows))
        return ("theme_source_themes,theme_members", len(theme_rows) + len(member_rows))
    if source.kind == "theme_page":
        tickers = extract_tickers_from_html(text, include_us=False)
        rows = _theme_member_rows(source, tickers)
        store.save("theme_members", HarvesterResult(tags={"date": TODAY}, data=rows))
        return ("theme_members", len(rows))
    if source.extractor == "csv_holdings":
        df = pd.read_csv(StringIO(text))
        rows = _etf_rows_from_frame(source, df)
        store.save("etf_holdings", HarvesterResult(tags={"date": TODAY}, data=rows))
        return ("etf_holdings", len(rows))
    tickers = extract_tickers_from_html(text, include_us=True)
    df = pd.DataFrame({"ticker": tickers})
    rows = _etf_rows_from_frame(source, df)
    store.save("etf_holdings", HarvesterResult(tags={"date": TODAY}, data=rows))
    return ("etf_holdings", len(rows))


def harvest_theme_sources(source_id: str | None = None, data_dir: str = DATA_DIR) -> list[dict]:
    sources = [get_theme_source(source_id)] if source_id else list_theme_sources()
    results = []
    for source in sources:
        dataset, rows = harvest_theme_source(source, data_dir)
        results.append({
            "source_id": source.source_id,
            "kind": source.kind,
            "theme_id": source.theme_id,
            "dataset": dataset,
            "rows": rows,
        })
    return results
