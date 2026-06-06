import glob
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional


def detect_lang(jp_text: str, en_text: str) -> str:
    """Return 'ja', 'en', or 'mixed' based on whether Japanese content is present."""
    has_jp = bool(re.search(r'[぀-ヿ一-鿿]', jp_text or ""))
    has_en = bool(en_text and en_text.strip())
    if has_jp and not has_en:
        return "ja"
    if has_jp and has_en:
        return "mixed"
    return "en"


def lang_instruction(lang: str) -> str:
    if lang == "ja":
        return "言語指定: 日本語で回答してください。"
    if lang == "mixed":
        return "Language: Respond in English (sources are mixed Japanese/English)."
    return "Language: Respond in English."

import pandas as pd

from elephant.river.tree import LAYER_LABELS, LAYERS, RiverTree

# LLM_PROVIDER: "anthropic" (default) or "openai"
# LLM_MODEL: override the default model for the chosen provider
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").lower()
LLM_MODEL = os.environ.get("LLM_MODEL", "")

_ANTHROPIC_DEFAULT = "claude-sonnet-4-6"
_OPENAI_DEFAULT = "gpt-4o"


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _make_client():
    if LLM_PROVIDER == "openai":
        import openai
        return openai.OpenAI()
    import anthropic
    return anthropic.Anthropic()


class Synthesizer:
    def __init__(self, data_dir: str, tickers_file: str, tree: Optional[RiverTree] = None):
        self.data_dir = data_dir
        self.tickers_file = tickers_file
        self.tree = tree
        self.client = _make_client()
        self.provider = LLM_PROVIDER

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

        if self.tree:
            lines.append("")
            lines.append("## Current River Tree (known instruments)")
            lines.append("Use this to avoid suggesting already-mapped tickers and to identify thin/empty layers.")
            for river in self.tree.list_rivers():
                by_layer = {layer: [] for layer in LAYERS}
                for node in river.nodes:
                    if node.layer in by_layer:
                        by_layer[node.layer].append(node.ticker)
                layer_parts = []
                for layer in LAYERS:
                    tickers = by_layer[layer]
                    status = ", ".join(tickers) if tickers else "(empty)"
                    layer_parts.append(f"{layer}: {status}")
                lines.append(f"  {river.name}: {' | '.join(layer_parts)}")

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

        jp_sources = " ".join(minkabu.values())
        en_sources = " ".join(item.get("title", "") for item in (news or []))
        lang = detect_lang(jp_sources, en_sources)

        river_context = ""
        if self.tree and self.tree.list_rivers():
            river_context = "\n\nThe investor uses a Thematic Supply Chain River framework with 4 layers:\n"
            river_context += "  source → upper → middle (highest alpha, 2-3x) → lower\n"
            river_context += "Known rivers: " + ", ".join(r.name for r in self.tree.list_rivers())
            river_context += "\nThe Current River Tree section in the data shows what is already mapped. "
            river_context += "Prioritize finding instruments for empty or thin layers."

        system_prompt = f"""\
You are a financial research scout writing a Daily Digest for a self-directed investor.

The investor's goal: discover stocks, sectors, or themes they haven't noticed yet — \
things they wouldn't have searched for because they didn't know they existed. \
They discovered stocks like NBIS and CLSK by browsing Yahoo Finance Japan BBS. \
That's the kind of discovery you're enabling.

The investor holds positions for weeks to months and does their own research after reading the digest.{river_context}

## Digest format

Start with: === Elephant Digest · {date_str} ===

Then 5 to 8 hints using these types:
- [NEW NAME]: a ticker not yet in the river tree, with unusual BBS activity or strong bull sentiment
- [RIVER GAP]: a layer in a known river that is empty or thin — suggest what type of instrument to look for
- [HOLDING SIGNAL]: sentiment staying strong despite a price drop — worth revisiting the thesis
- [SECTOR THEME]: multiple tickers in the same sector showing similar signals
- [MACRO OBSERVATION]: a macro or currency angle worth watching

Each hint: 3 to 5 lines. End with "→ Worth looking at..." or "→ Worth checking..."
State which signal triggered each hint (BBS rank position, bull ratio, Minkabu consensus, etc.)
Do not suggest tickers already in the river tree unless it is a holding signal.
Tone: opinionated but humble. "Worth looking at" not "Buy this."
{lang_instruction(lang)}\
"""

        if self.provider == "openai":
            model = LLM_MODEL or _OPENAI_DEFAULT
            response = self.client.chat.completions.create(
                model=model,
                max_tokens=1500,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context},
                ],
            )
            return response.choices[0].message.content
        else:
            model = LLM_MODEL or _ANTHROPIC_DEFAULT
            response = self.client.messages.create(
                model=model,
                max_tokens=1500,
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": context}],
            )
            return response.content[0].text
