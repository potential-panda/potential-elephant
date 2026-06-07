"""
Deep Dive: full research brief on a single ticker.

Collects: yfinance fundamentals + price history, BBS sentiment trend,
recent BBS comments, Minkabu analyst consensus, news mentions, river
tree position — then calls the LLM for a structured brief.
"""

import glob
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from elephant.river.tree import LAYERS, RiverTree
from elephant.synthesizer import (
    LLM_MODEL,
    LLM_PROVIDER,
    _ANTHROPIC_DEFAULT,
    _OPENAI_DEFAULT,
    _make_client,
    _strip_html,
    detect_lang,
    lang_instruction,
)


class Diver:
    def __init__(self, data_dir: str, tree: Optional[RiverTree] = None):
        self.data_dir = data_dir
        self.tree = tree
        self.client = _make_client()
        self.provider = LLM_PROVIDER

    # --- Data loaders ---

    def _normalise(self, ticker: str) -> tuple[str, str]:
        """Return (ticker_with_T, ticker_without_T)."""
        if ticker.endswith(".T"):
            return ticker, ticker[:-2]
        return f"{ticker}.T", ticker

    def _load_price(self, ticker: str) -> dict:
        try:
            import yfinance as yf

            t = yf.Ticker(ticker)
            info = t.info or {}
            hist = t.history(period="3mo")

            result = {
                "name": info.get("longName") or info.get("shortName", ticker),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "description": (info.get("longBusinessSummary") or "")[:600],
                "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "week52_high": info.get("fiftyTwoWeekHigh"),
                "week52_low": info.get("fiftyTwoWeekLow"),
                "market_cap": info.get("marketCap"),
                "currency": info.get("currency", ""),
            }

            if not hist.empty:
                result["price_1mo_ago"] = float(hist["Close"].iloc[0]) if len(hist) >= 20 else None
                result["price_now"] = float(hist["Close"].iloc[-1])
                result["vol_avg_30d"] = float(hist["Volume"].tail(30).mean())
                result["vol_latest"] = float(hist["Volume"].iloc[-1])
                result["price_history"] = hist["Close"].tail(10).to_dict()

            return result
        except Exception:
            logging.exception(f"yfinance failed for {ticker}")
            return {}

    def _load_evaluations(self, ticker_t: str) -> pd.DataFrame:
        pattern = os.path.join(
            self.data_dir, "dataset=yahoo_evaluations",
            f"ticker={ticker_t}", "**", "data.parquet",
        )
        files = glob.glob(pattern, recursive=True)
        if not files:
            return pd.DataFrame()
        try:
            df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
            df["scraped_at"] = pd.to_datetime(df["scraped_at"])
            df["bull"] = df["strongest"] + df["strong"]
            df["bear"] = df["weak"] + df["weakest"]
            return df.sort_values("scraped_at")
        except Exception:
            return pd.DataFrame()

    def _load_comments(self, ticker_t: str, n: int = 30) -> list[str]:
        pattern = os.path.join(
            self.data_dir, "dataset=yahoo_comments",
            f"ticker={ticker_t}", "**", "data.parquet",
        )
        files = glob.glob(pattern, recursive=True)
        if not files:
            return []
        try:
            df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
            df["scraped_at"] = pd.to_datetime(df["scraped_at"])
            recent = df.sort_values("scraped_at", ascending=False).head(n)
            return [str(r["body"]) for _, r in recent.iterrows() if r.get("body")]
        except Exception:
            return []

    def _load_minkabu(self, ticker_t: str) -> str:
        year = datetime.now().strftime("%Y")
        path = os.path.join(
            self.data_dir, "dataset=minkabu_raw_html",
            f"ticker={ticker_t}", f"YEAR={year}", "data.parquet",
        )
        if not os.path.exists(path):
            return ""
        try:
            df = pd.read_parquet(path).sort_values("scraped_at", ascending=False)
            if df.empty:
                return ""
            latest = df.iloc[0]
            text = _strip_html(str(latest.get("analyst_consensus", "")))
            return text[:2000] if len(text) > 100 else ""
        except Exception:
            return ""

    def _load_news(self, ticker: str, ticker_t: str) -> list[str]:
        bare = ticker_t.replace(".T", "")
        pattern = os.path.join(self.data_dir, "dataset=news_headlines", "date=*", "data.parquet")
        files = glob.glob(pattern)
        if not files:
            return []
        try:
            since = datetime.now() - timedelta(days=7)
            dfs = []
            for f in files:
                df = pd.read_parquet(f)
                df["scraped_at"] = pd.to_datetime(df["scraped_at"])
                dfs.append(df[df["scraped_at"] >= since])
            combined = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=["id"])
            # filter headlines mentioning the ticker or its bare number
            mask = combined["title"].str.contains(bare, case=False, na=False)
            if not mask.any():
                return []
            return combined[mask]["title"].head(10).tolist()
        except Exception:
            return []

    def _river_position(self, ticker_t: str) -> str:
        if not self.tree:
            return "River tree not loaded."
        matches = self.tree.find_ticker(ticker_t)
        if matches:
            parts = []
            for river, node in matches:
                parts.append(f"Already in river '{river.name}' at layer '{node.layer}': {node.role}")
            return "\n".join(parts)
        return "Not currently in the river tree."

    # --- Context builder ---

    def _build_context(self, ticker: str) -> str:
        ticker_t, bare = self._normalise(ticker)
        lines = [f"Deep Dive: {ticker_t}", f"Date: {datetime.now().strftime('%Y-%m-%d')}", ""]

        price = self._load_price(ticker_t)
        if price:
            lines.append("## Company")
            lines.append(f"Name: {price.get('name', ticker_t)}")
            if price.get("sector"):
                lines.append(f"Sector: {price['sector']} / {price.get('industry', '')}")
            if price.get("description"):
                lines.append(f"Description: {price['description']}")
            lines.append("")
            lines.append("## Price")
            cur = price.get("current_price")
            hi = price.get("week52_high")
            lo = price.get("week52_low")
            p1m = price.get("price_1mo_ago")
            if cur:
                lines.append(f"Current: {cur} {price.get('currency','')}")
            if hi and lo:
                pct_from_hi = ((cur - hi) / hi * 100) if cur and hi else None
                pct_from_lo = ((cur - lo) / lo * 100) if cur and lo else None
                lines.append(f"52w range: {lo} – {hi}" +
                    (f"  (now {pct_from_hi:+.0f}% from high, {pct_from_lo:+.0f}% from low)" if pct_from_hi is not None else ""))
            if p1m and cur:
                chg = (cur - p1m) / p1m * 100
                lines.append(f"1-month change: {chg:+.1f}%")
            vol = price.get("vol_latest")
            avg = price.get("vol_avg_30d")
            if vol and avg and avg > 0:
                lines.append(f"Volume vs 30d avg: {vol/avg:.1f}x")
            if price.get("market_cap"):
                mc = price["market_cap"]
                lines.append(f"Market cap: ¥{mc/1e8:.0f}億" if price.get("currency") == "JPY" else f"Market cap: ${mc/1e9:.1f}B")
        lines.append("")

        evals = self._load_evaluations(ticker_t)
        if not evals.empty:
            lines.append("## BBS Sentiment Trend (Yahoo Finance JP)")
            recent = evals.tail(10)
            for _, row in recent.iterrows():
                date = row["scraped_at"].strftime("%m-%d")
                lines.append(f"  {date}  Bull {row['bull']:.0f}%  Bear {row['bear']:.0f}%  Neutral {row['both']:.0f}%")
            avg_bull = recent["bull"].mean()
            trend = "rising" if recent["bull"].iloc[-1] > recent["bull"].iloc[0] else "falling"
            lines.append(f"  → Avg bull {avg_bull:.0f}%, trend {trend}")
        lines.append("")

        comments = self._load_comments(ticker_t, n=20)
        if comments:
            lines.append("## Recent BBS Comments (sample)")
            for c in comments[:15]:
                lines.append(f"  - {c[:200]}")
        lines.append("")

        minkabu = self._load_minkabu(ticker_t)
        if minkabu:
            lines.append("## Minkabu Analyst Consensus")
            lines.append(minkabu)
        lines.append("")

        news = self._load_news(ticker, ticker_t)
        if news:
            lines.append("## Recent News Mentions")
            for n in news:
                lines.append(f"  - {n}")
        lines.append("")

        lines.append("## River Tree Position")
        lines.append(self._river_position(ticker_t))

        return "\n".join(lines)

    # --- LLM call ---

    def _llm(self, system: str, user: str) -> str:
        if self.provider == "openai":
            model = LLM_MODEL or _OPENAI_DEFAULT
            response = self.client.chat.completions.create(
                model=model,
                max_tokens=1800,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.choices[0].message.content
        else:
            model = LLM_MODEL or _ANTHROPIC_DEFAULT
            response = self.client.messages.create(
                model=model,
                max_tokens=1800,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text

    # --- Public ---

    def _links_section(self, ticker_t: str) -> str:
        bare = ticker_t.replace(".T", "")
        return (
            "\n\n---\n## Links\n"
            f"- [Yahoo Finance BBS](https://finance.yahoo.co.jp/quote/{ticker_t}/forum)\n"
            f"- [Yahoo Finance Quote](https://finance.yahoo.co.jp/quote/{ticker_t})\n"
            f"- [Minkabu](https://minkabu.jp/stock/{bare})\n"
            f"- [TDnet](https://www.release.tdnet.info/)\n"
        )

    def dive(self, ticker: str) -> str:
        ticker_t = ticker if ticker.endswith(".T") else f"{ticker}.T"
        context = self._build_context(ticker)
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Detect language from JP sources (comments + Minkabu) vs EN sources (news)
        comments = self._load_comments(ticker_t)
        minkabu = self._load_minkabu(ticker_t)
        news = self._load_news(ticker, ticker_t)
        jp_sources = " ".join(comments) + " " + minkabu
        en_sources = " ".join(news)
        lang = detect_lang(jp_sources, en_sources)

        system = f"""\
You are a financial research analyst writing a Deep Dive brief for a self-directed investor.
The investor holds positions for weeks to months and does their own final research.
They want to understand: what this company actually does, why the BBS community is interested,
whether the sentiment is credible or just momentum noise, and where it fits in the
Thematic Supply Chain River framework (source → upper → middle → lower).

Write a structured brief with these sections:

=== Deep Dive: {ticker_t} · {date_str} ===

## What It Is
2–3 sentences: core business, sector, market position.

## Why BBS Is Talking About It
What's driving community interest? Is it fundamental or speculative momentum?

## Sentiment Read
Interpret the BBS bull/bear trend. Is the conviction rising, fading, or noisy?
Note any qualitative signals from the comments.

## Price Context
Key price observations: where it sits in its 52w range, recent momentum, volume signal.

## River Fit
Does this belong in one of the 4 rivers (ai_infra, tech_local, physical_ai, longevity)?
Which layer? Or is it a speculative outlier with no clean fit?

## Verdict
3–5 sentences. Worth investigating further, or noise? What would change your mind?
End with one of: → Add to watchlist | → River candidate: [river/layer] | → Pass for now

Style: direct and honest. Flag speculation clearly. "Worth investigating" not "Buy this."
{lang_instruction(lang)}\
"""

        brief = self._llm(system, context)
        return brief + self._links_section(ticker_t)
