from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta

import pandas as pd

from elephant.river.tree import LAYERS, RiverTree
from elephant.synthesizer import LLM_MODEL, LLM_PROVIDER, _ANTHROPIC_DEFAULT, _OPENAI_DEFAULT, _make_client


class Discoverer:
    def __init__(self, data_dir: str, tickers_file: str, tree: RiverTree):
        self.data_dir = data_dir
        self.tickers_file = tickers_file
        self.tree = tree
        self.client = _make_client()
        self.provider = LLM_PROVIDER

    def _llm(self, prompt: str, max_tokens: int = 600) -> str:
        if self.provider == "openai":
            model = LLM_MODEL or _OPENAI_DEFAULT
            response = self.client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        else:
            model = LLM_MODEL or _ANTHROPIC_DEFAULT
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

    # --- Signal loading ---

    def _load_ticker_signals(self, ticker: str) -> str:
        """Collect available BBS + Minkabu signals for a single ticker."""
        lines = [f"Ticker: {ticker}"]
        year = datetime.now().strftime("%Y")

        # Normalise ticker: try with .T suffix for JP stocks
        ticker_t = ticker if ticker.endswith(".T") else f"{ticker}.T"

        for t in [ticker, ticker_t]:
            eval_path = os.path.join(
                self.data_dir, "dataset=yahoo_evaluations",
                f"ticker={t}", f"YEAR={year}", "data.parquet",
            )
            if os.path.exists(eval_path):
                try:
                    df = pd.read_parquet(eval_path).sort_values("scraped_at", ascending=False)
                    if not df.empty:
                        row = df.iloc[0]
                        bull = float(row.get("strongest") or 0) + float(row.get("strong") or 0)
                        lines.append(f"Yahoo JP BBS sentiment — Bull: {bull:.0f}%")
                except Exception:
                    pass
                break

            mk_path = os.path.join(
                self.data_dir, "dataset=minkabu_raw_html",
                f"ticker={t}", f"YEAR={year}", "data.parquet",
            )
            if os.path.exists(mk_path):
                try:
                    df = pd.read_parquet(mk_path).sort_values("scraped_at", ascending=False)
                    if not df.empty:
                        raw = str(df.iloc[0].get("analyst_consensus", ""))
                        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()
                        lines.append(f"Minkabu analyst consensus: {text[:500]}")
                except Exception:
                    pass
                break

        return "\n".join(lines)

    def _load_news_for_keyword(self, keyword: str, since: datetime) -> list[str]:
        """Return recent headlines matching a keyword."""
        import glob
        pattern = os.path.join(self.data_dir, "dataset=news_headlines", "date=*", "data.parquet")
        files = glob.glob(pattern)
        matches = []
        kw_lower = keyword.lower()
        for f in files:
            try:
                df = pd.read_parquet(f)
                df["scraped_at"] = pd.to_datetime(df["scraped_at"])
                recent = df[df["scraped_at"] >= since]
                for _, row in recent.iterrows():
                    title = str(row.get("title", ""))
                    summary = str(row.get("summary", ""))
                    if kw_lower in title.lower() or kw_lower in summary.lower():
                        matches.append(f"[{row.get('source','')}] {title}")
            except Exception:
                pass
        return matches[:20]

    # --- River tree context ---

    def _tree_summary(self) -> str:
        lines = ["Current river tree (what is already mapped):"]
        for river in self.tree.list_rivers():
            node_str = ", ".join(f"{n.ticker}[{n.layer}]" for n in river.nodes)
            lines.append(f"  {river.id} ({river.name}): {node_str or '(empty)'}")
        return "\n".join(lines)

    # --- Claude classification ---

    def _classify(self, ticker: str, extra_context: str = "") -> dict:
        signals = self._load_ticker_signals(ticker)
        tree_summary = self._tree_summary()

        prompt = f"""\
You are a financial analyst classifying a stock into a thematic supply chain river framework.

Layer definitions:
  source  — Where CapEx or policy funding originates (hyperscalers, government mandates)
  upper   — Core designers absorbing the initial capital surge (e.g., GPU designers, foundries)
  middle  — Specialized suppliers where physical bottlenecks emerge (highest alpha, 2-3x potential)
  lower   — Real-world capacity constraints sustaining the trend (power, logistics, infrastructure)

{tree_summary}

Known river IDs and themes:
  ai_infra    — AI Infrastructure Supercycle (Hyperscaler CapEx → compute → power)
  tech_local  — Tech Localization & Onshoring (geopolitics → precision tools → industrial RE)
  physical_ai — Embodied Physical AI (edge AI → actuators/sensors → automation)
  longevity   — Demographic Longevity (GLP-1/clinical → APIs/injectors → cold chain)

Available signals for {ticker}:
{signals}
{extra_context}

Respond ONLY with valid JSON, no other text:
{{
  "ticker": "{ticker}",
  "fits_existing_river": true or false,
  "river_id": "<river id or null>",
  "new_river_name": "<suggest a name only if fits_existing_river is false and a new river is warranted, else null>",
  "layer": "<source|upper|middle|lower or null>",
  "name": "<company full name>",
  "market": "<US or JP>",
  "role": "<one sentence: what this company does in the supply chain>",
  "confidence": "<high|medium|low>",
  "reasoning": "<2-3 sentences explaining the classification>"
}}"""

        raw = self._llm(prompt, max_tokens=600)
        try:
            start, end = raw.find("{"), raw.rfind("}") + 1
            return json.loads(raw[start:end])
        except Exception:
            logging.error(f"Failed to parse classification response for {ticker}: {raw}")
            return {}

    # --- Public interface ---

    def classify_ticker(self, ticker: str) -> dict:
        """Classify a single ticker and return the suggestion dict."""
        return self._classify(ticker)

    def classify_keyword(self, keyword: str) -> list[dict]:
        """Find tickers mentioned in news matching keyword and classify them."""
        since = datetime.now() - timedelta(hours=72)
        headlines = self._load_news_for_keyword(keyword, since)
        if not headlines:
            print(f"No recent news found for keyword: '{keyword}'")
            return []

        # Ask Claude to extract tickers from the headlines
        extract_prompt = f"""\
From the following news headlines, extract all stock ticker symbols or company names mentioned.
Return ONLY a JSON array of ticker symbols (e.g. ["NVDA", "6723.T", "AMD"]).
If none, return [].

Headlines:
{chr(10).join(headlines)}"""

        raw = self._llm(extract_prompt, max_tokens=200)
        try:
            start, end = raw.find("["), raw.rfind("]") + 1
            tickers = json.loads(raw[start:end])
        except Exception:
            print("Could not extract tickers from headlines.")
            return []

        news_context = "Relevant headlines:\n" + "\n".join(headlines[:10])
        results = []
        for t in tickers[:5]:
            result = self._classify(t, extra_context=news_context)
            if result:
                results.append(result)
        return results

    def scan_unknown_tickers(self) -> list[dict]:
        """Scan BBS hot tickers not yet in the tree and classify them."""
        if not os.path.exists(self.tickers_file):
            return []
        with open(self.tickers_file) as f:
            hot_tickers = [line.strip() for line in f if line.strip()]

        known = {n.ticker for river in self.tree.list_rivers() for n in river.nodes}
        # Check both with and without .T suffix
        known_base = {t.replace(".T", "") for t in known}
        unknown = [
            t for t in hot_tickers[:30]
            if t not in known and t.replace(".T", "") not in known_base
        ]

        suggestions = []
        for ticker in unknown[:10]:  # limit API calls per run
            result = self._classify(ticker)
            if result and result.get("fits_existing_river") and result.get("confidence") in ("high", "medium"):
                suggestions.append(result)
                logging.info(
                    f"[Discover] {ticker} → {result.get('river_id')} "
                    f"[{result.get('layer')}] confidence={result.get('confidence')}"
                )
        return suggestions
