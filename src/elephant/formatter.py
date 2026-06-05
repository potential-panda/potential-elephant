"""
Format digest text with clickable ticker links.

JP tickers (e.g. 7011.T) → Yahoo Finance Japan
US tickers (e.g. NVDA)   → Yahoo Finance US
"""

import html
import re

JP_RE = re.compile(r'\b(\d{4}\.T)\b')
US_RE = re.compile(r'\b([A-Z]{2,5})\b')

# Common non-ticker uppercase words to skip
_US_SKIP = {
    # Digest hint type labels
    "NEW", "NAME", "RIVER", "GAP", "HOLDING", "SIGNAL", "SECTOR",
    "THEME", "MACRO", "OBSERVATION",
    # Common English words
    "BBS", "JP", "US", "ETF", "AI", "AND", "OR", "NOT", "THE", "FOR",
    "IN", "AT", "LLC", "LTD", "INC", "CO", "NO", "SO", "API",
    "RSS", "CEO", "IPO", "GDP", "BOJ", "FED", "EUV", "GPU", "DRAM",
    "HBM", "URL", "ID", "VC", "PE", "PB", "ROE", "ROA",
    "JPY", "USD", "EUR", "GBP", "CNY", "KRW",
    "WORTH", "LOOKING", "CHECKING", "MULTIPLE", "RECENT", "STRONG",
}


def _jp_url(ticker: str) -> str:
    return f"https://finance.yahoo.co.jp/quote/{ticker}"


def _us_url(ticker: str) -> str:
    return f"https://finance.yahoo.com/quote/{ticker}"


def to_html(text: str) -> str:
    """Convert plain-text digest to HTML with clickable ticker links."""
    escaped = html.escape(text)

    escaped = JP_RE.sub(
        lambda m: f'<a href="{_jp_url(m.group(1))}">{m.group(1)}</a>',
        escaped,
    )

    def _us_sub(m: re.Match) -> str:
        t = m.group(1)
        return t if t in _US_SKIP else f'<a href="{_us_url(t)}">{t}</a>'

    escaped = US_RE.sub(_us_sub, escaped)

    return (
        "<!DOCTYPE html><html><body>"
        "<pre style='font-family:monospace;white-space:pre-wrap;line-height:1.6'>"
        f"{escaped}"
        "</pre></body></html>"
    )


def to_markdown(text: str) -> str:
    """Add markdown hyperlinks to tickers (for Discord)."""
    text = JP_RE.sub(lambda m: f"[{m.group(1)}]({_jp_url(m.group(1))})", text)

    def _us_sub(m: re.Match) -> str:
        t = m.group(1)
        return t if t in _US_SKIP else f"[{t}]({_us_url(t)})"

    return US_RE.sub(_us_sub, text)
