import glob
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

import anthropic
import pandas as pd


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class Synthesizer:
    def __init__(self, data_dir: str, tickers_file: str):
        self.data_dir = data_dir
        self.tickers_file = tickers_file
        self.client = anthropic.Anthropic()

    def _load_tickers(self) -> list[str]:
        if not os.path.exists(self.tickers_file):
            return []
        with open(self.tickers_file) as f:
            return [line.strip() for line in f if line.strip()]

    def _load_evaluations(self, tickers: list[str], since: datetime) -> dict[str, dict]:
        results = {}
        year = datetime.now().strftime("%Y")
        for ticker in tickers:
            path = os.path.join(
                self.data_dir, "dataset=yahoo_evaluations",
                f"ticker={ticker}", f"YEAR={year}", "data.parquet",
            )
            if not os.path.exists(path):
                continue
            try:
                df = pd.read_parquet(path)
                df["scraped_at"] = pd.to_datetime(df["scraped_at"])
                recent = df[df["scraped_at"] >= since].sort_values("scraped_at")
                if recent.empty:
                    continue
                latest = recent.iloc[-1]
                results[ticker] = {
                    "strongest": float(latest.get("strongest") or 0),
                    "strong": float(latest.get("strong") or 0),
                    "both": float(latest.get("both") or 0),
                    "weak": float(latest.get("weak") or 0),
                    "weakest": float(latest.get("weakest") or 0),
                }
            except Exception:
                logging.exception(f"Failed to load evaluations for {ticker}")
        return results

    def _load_news(self, since: datetime) -> list[dict]:
        pattern = os.path.join(self.data_dir, "dataset=news_headlines", "date=*", "data.parquet")
        files = glob.glob(pattern)
        if not files:
            return []

        dfs = []
        for f in files:
            try:
                df = pd.read_parquet(f)
                df["scraped_at"] = pd.to_datetime(df["scraped_at"])
                recent = df[df["scraped_at"] >= since]
                if not recent.empty:
                    dfs.append(recent)
            except Exception:
                logging.exception(f"Failed to load news from {f}")

        if not dfs:
            return []

        combined = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=["id"])
        combined = combined.sort_values("scraped_at", ascending=False)
        return combined.head(60).to_dict("records")

    def _load_minkabu(self, tickers: list[str], since: datetime) -> dict[str, str]:
        results = {}
        year = datetime.now().strftime("%Y")
        for ticker in tickers:
            path = os.path.join(
                self.data_dir, "dataset=minkabu_raw_html",
                f"ticker={ticker}", f"YEAR={year}", "data.parquet",
            )
            if not os.path.exists(path):
                continue
            try:
                df = pd.read_parquet(path)
                df["scraped_at"] = pd.to_datetime(df["scraped_at"])
                recent = df[df["scraped_at"] >= since].sort_values("scraped_at")
                if recent.empty:
                    continue
                latest = recent.iloc[-1]
                # analyst_consensus is the most signal-dense page for the digest
                text = _strip_html(str(latest.get("analyst_consensus", "")))
                if len(text) > 200:
                    results[ticker] = text[:1500]
            except Exception:
                logging.exception(f"Failed to load Minkabu data for {ticker}")
        return results

    def _build_context(
        self,
        tickers: list[str],
        evaluations: dict[str, dict],
        minkabu: dict[str, str],
        news: Optional[list[dict]] = None,
    ) -> str:
        lines = []
        date_str = datetime.now().strftime("%Y-%m-%d")
        lines.append(f"Today: {date_str}")
        lines.append("")
        lines.append("## BBS Hot Tickers (ranked by discussion volume)")
        lines.append("Source: Yahoo Finance Japan BBS activity ranking.")
        lines.append("")

        for i, ticker in enumerate(tickers[:40], 1):
            ev = evaluations.get(ticker)
            if ev:
                bull = ev["strongest"] + ev["strong"]
                bear = ev["weak"] + ev["weakest"]
                neutral = ev["both"]
                lines.append(f"{i:2}. {ticker}  Bull {bull:.0f}% | Neutral {neutral:.0f}% | Bear {bear:.0f}%")
            else:
                lines.append(f"{i:2}. {ticker}")

        if minkabu:
            lines.append("")
            lines.append("## Minkabu Analyst Consensus (recent data)")
            for ticker, text in list(minkabu.items())[:15]:
                lines.append(f"\n### {ticker}")
                lines.append(text)

        if news:
            lines.append("")
            lines.append("## Recent News Headlines (past 48h)")
            lines.append("Sources: NHK Business, Reuters, Google News (JP economy, semiconductors, AI infrastructure)")
            lines.append("")
            for item in news[:50]:
                source = item.get("source", "")
                title = item.get("title", "")
                summary = (item.get("summary") or "")[:200]
                lines.append(f"- [{source}] {title}")
                if summary:
                    lines.append(f"  {summary}")

        return "\n".join(lines)

    def generate(self) -> str:
        since = datetime.now() - timedelta(hours=48)
        tickers = self._load_tickers()

        if not tickers:
            return "No tickers found. Run `python src/cli.py fetch --dataset yjp_bbs_rank` first."

        evaluations = self._load_evaluations(tickers, since)
        minkabu = self._load_minkabu(tickers, since)
        news = self._load_news(since)
        context = self._build_context(tickers, evaluations, minkabu, news)
        date_str = datetime.now().strftime("%Y-%m-%d")

        system_prompt = f"""\
You are a financial research scout writing a Daily Digest for a self-directed investor.

The investor's goal: discover stocks, sectors, or themes they haven't noticed yet — \
things they wouldn't have searched for because they didn't know they existed. \
They discovered stocks like NBIS and CLSK by browsing Yahoo Finance Japan BBS. \
That's the kind of discovery you're enabling.

The investor holds positions for weeks to months and does their own research after reading the digest.

## Digest format

Start with: === Elephant Digest · {date_str} ===

Then 5 to 8 hints using these types:
- [NEW NAME]: a ticker the investor likely doesn't know, with unusual BBS activity or strong bull sentiment
- [HOLDING SIGNAL]: sentiment staying strong despite a price drop — worth revisiting the thesis
- [SECTOR THEME]: multiple tickers in the same sector showing similar signals
- [MACRO OBSERVATION]: a macro or currency angle worth watching

Each hint: 3 to 5 lines. End with "→ Worth looking at..." or "→ Worth checking..."
State which signal triggered each hint (BBS rank position, bull ratio, Minkabu consensus, etc.)
Prioritize names the investor likely doesn't follow yet.
If a ticker is a small or mid-cap that rarely gets attention, flag that.
Language: opinionated but humble. "Worth looking at" not "Buy this."\
"""

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
        )

        return response.content[0].text
