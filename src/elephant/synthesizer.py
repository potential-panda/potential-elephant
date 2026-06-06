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

    def _load_tdnet(self, tickers: list[str], since: datetime) -> list[dict]:
        pattern = os.path.join(self.data_dir, "dataset=tdnet_disclosures", "date=*", "data.parquet")
        files = glob.glob(pattern)
        if not files:
            return []
        ticker_set = set(tickers)
        dfs = []
        for f in files:
            try:
                df = pd.read_parquet(f)
                df["scraped_at"] = pd.to_datetime(df["scraped_at"])
                recent = df[df["scraped_at"] >= since]
                if not recent.empty:
                    dfs.append(recent)
            except Exception:
                logging.exception(f"Failed to load TDnet data from {f}")
        if not dfs:
            return []
        combined = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=["id"])
        combined = combined[combined["ticker"].isin(ticker_set)]
        combined = combined.sort_values(["date", "time"], ascending=False)
        return combined.head(30).to_dict("records")

    def _load_speed(self, tickers: list[str]) -> dict[str, list]:
        """Return {ticker: [latest, prev]} comments/hour entries from the registry."""
        from elephant.ticker_registry import load_cache
        cache = load_cache(self.tickers_file)
        result = {}
        for ticker in tickers:
            entry = cache.get(ticker)
            if not entry or not isinstance(entry, dict):
                continue
            history = entry.get("speed_history", [])
            if history:
                result[ticker] = history[:3]  # keep up to 3 most recent days
        return result

    def _load_prices(self, tickers: list[str]) -> dict[str, dict]:
        if not tickers:
            return {}
        try:
            import yfinance as yf
            hist = yf.download(tickers, period="1mo", progress=False, auto_adjust=True)
            if hist.empty:
                return {}
            closes = hist["Close"]
            if not hasattr(closes, "columns"):
                closes = closes.to_frame(name=tickers[0])
            result = {}
            for ticker in tickers:
                if ticker not in closes.columns:
                    continue
                series = closes[ticker].dropna()
                if len(series) < 2:
                    continue
                price_now = float(series.iloc[-1])
                price_1mo = float(series.iloc[0])
                result[ticker] = {
                    "price": price_now,
                    "chg_1mo": (price_now - price_1mo) / price_1mo * 100,
                }
            return result
        except Exception:
            logging.exception("Failed to load prices for digest")
            return {}

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

    def _build_jp_context(
        self,
        tickers: list[str],
        evaluations: dict[str, dict],
        minkabu: dict[str, str],
        prices: dict[str, dict],
        speed: dict[str, list],
        tdnet: list[dict],
    ) -> str:
        lines = [f"Today: {datetime.now().strftime('%Y-%m-%d')}", ""]
        lines.append("## BBS Hot Tickers (Yahoo Finance Japan — ranked by discussion volume)")
        lines.append("Columns: BBS rank | ticker | sentiment | 1-month price change | comment speed (c/h, newest first)")
        lines.append("")
        for i, ticker in enumerate(tickers[:40], 1):
            ev = evaluations.get(ticker)
            pr = prices.get(ticker)
            sp = speed.get(ticker)
            sentiment = ""
            if ev:
                bull = ev["strongest"] + ev["strong"]
                bear = ev["weak"] + ev["weakest"]
                sentiment = f"Bull {bull:.0f}% | Neutral {ev['both']:.0f}% | Bear {bear:.0f}%"
            price_str = f"{pr['chg_1mo']:+.1f}% 1mo" if pr else ""
            speed_str = ""
            if sp:
                speed_str = "speed " + " → ".join(f"{h['comments_per_hour']:.1f}" for h in sp)
            parts = [sentiment, price_str, speed_str]
            suffix = "  |  ".join(p for p in parts if p)
            lines.append(f"{i:2}. {ticker}  {suffix}".rstrip())
        if tdnet:
            lines.append("")
            lines.append("## 適時開示（TDnet）— 直近48h・監視銘柄のみ")
            for item in tdnet:
                lines.append(f"  [{item['date']} {item['time']}] {item['ticker']} {item['company']} — {item['title']}")
        if minkabu:
            lines.append("")
            lines.append("## Minkabu アナリストコンセンサス（直近データ）")
            for ticker, text in list(minkabu.items())[:15]:
                lines.append(f"\n### {ticker}")
                lines.append(text)
        return "\n".join(lines)

    def _build_en_context(self, news: list[dict]) -> str:
        lines = [f"Today: {datetime.now().strftime('%Y-%m-%d')}", ""]
        lines.append("## Recent News Headlines (past 48h)")
        lines.append("Sources: NHK Business, Google News (JP economy, semiconductors, AI infrastructure, robotics, pharma)")
        lines.append("")
        for item in news[:60]:
            source = item.get("source", "")
            title = item.get("title", "")
            summary = (item.get("summary") or "")[:200]
            lines.append(f"- [{source}] {title}")
            if summary:
                lines.append(f"  {summary}")
        if self.tree:
            lines.append("")
            lines.append("## Current River Tree (known instruments)")
            lines.append("Use this to identify thin/empty layers for RIVER GAP hints.")
            for river in self.tree.list_rivers():
                by_layer = {layer: [] for layer in LAYERS}
                for node in river.nodes:
                    if node.layer in by_layer:
                        by_layer[node.layer].append(node.ticker)
                layer_parts = []
                for layer in LAYERS:
                    t = by_layer[layer]
                    layer_parts.append(f"{layer}: {', '.join(t) if t else '(empty)'}")
                lines.append(f"  {river.name}: {' | '.join(layer_parts)}")
        return "\n".join(lines)

    def _llm(self, system: str, context: str, max_tokens: int = 900) -> str:
        if self.provider == "openai":
            model = LLM_MODEL or _OPENAI_DEFAULT
            resp = self.client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": context}],
            )
            return resp.choices[0].message.content
        else:
            model = LLM_MODEL or _ANTHROPIC_DEFAULT
            resp = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": context}],
            )
            return resp.content[0].text

    def generate(self) -> str:
        since = datetime.now() - timedelta(hours=48)
        tickers = self._load_tickers()

        if not tickers:
            return "No tickers found. Run `python src/cli.py fetch --dataset yjp_bbs_rank` first."

        evaluations = self._load_evaluations(tickers, since)
        minkabu = self._load_minkabu(tickers, since)
        news = self._load_news(since)
        prices = self._load_prices(tickers[:40])
        speed = self._load_speed(tickers[:40])
        tdnet = self._load_tdnet(tickers, since)
        date_str = datetime.now().strftime("%Y-%m-%d")

        river_context = ""
        if self.tree and self.tree.list_rivers():
            river_context = "\nKnown rivers: " + ", ".join(r.name for r in self.tree.list_rivers())
            river_context += "\nLayers: source → upper → middle (highest alpha) → lower"

        # --- Call 1: Japanese hints from BBS + Minkabu ---
        jp_system = f"""\
あなたは自己投資家向けのデイリーダイジェストを書く金融リサーチスカウトです。

投資家の目標：まだ気づいていない銘柄・セクター・テーマを発見すること。
保有期間は数週間〜数ヶ月。ヒントを見てから自分で調査します。{river_context}

## 出力フォーマット

以下のヒントタイプから3〜4件、日本語で書いてください：
- [NEW NAME]: リバーツリーにない銘柄で、BBS活動が異常に高い、コメント速度（c/h）が急加速している、または強気センチメントが強い
- [HOLDING SIGNAL]: 直近1ヶ月で株価が下落（1mo欄がマイナス）しているにも関わらず、強気センチメントが高い水準を維持している銘柄 — 底堅さの確認価値あり
- [SECTOR THEME]: 同じセクターの複数銘柄が類似したシグナルを示している

コメント速度（speed欄）の読み方：「最新 → 前日 → 前々日」の順。急加速（例：1.2 → 3.5 → 8.0）は注目に値する。

各ヒント：3〜5行。「→ 注目の価値あり」または「→ 確認の価値あり」で締めること。
どのシグナルがヒントのトリガーになったか明記（BBS順位、強気比率、コメント速度、TDnet開示、Minkabuコンセンサスなど）。
適時開示（TDnet）がある銘柄は、開示内容がセンチメントと一致しているか相反しているかを必ず確認すること。
リバーツリーにある銘柄はHOLDING SIGNALでない限り提案しないこと。
トーン：意見ははっきりと、でも謙虚に。「注目の価値あり」であって「買え」ではない。
ヘッダー行は出力しないこと（=== Elephant Digest... の行は不要）。\
"""

        # --- Call 2: English hints from news + river tree ---
        en_system = f"""\
You are a financial research scout writing part of a Daily Digest for a self-directed investor.
The investor holds positions for weeks to months and does their own research after reading the digest.{river_context}

Write 2 to 3 hints in English based ONLY on the news headlines and river tree below.
Use these hint types:
- [RIVER GAP]: a layer in a known river that is empty or thin — suggest what type of instrument to look for
- [MACRO OBSERVATION]: a macro, currency, or geopolitical angle worth watching
- [SECTOR THEME]: a theme emerging from multiple news items pointing at the same supply chain layer

Each hint: 3 to 5 lines. End with "→ Worth looking at..." or "→ Worth checking..."
State which news items or river gap triggered the hint.
Do not suggest tickers already in the river tree.
Tone: opinionated but humble.
Do NOT output a header line (no === Elephant Digest... line).\
"""

        jp_hints = self._llm(jp_system, self._build_jp_context(tickers, evaluations, minkabu, prices, speed, tdnet))
        en_hints = self._llm(en_system, self._build_en_context(news))

        return (
            f"=== Elephant Digest · {date_str} ===\n\n"
            f"{jp_hints.strip()}\n\n"
            f"---\n\n"
            f"{en_hints.strip()}"
        )
