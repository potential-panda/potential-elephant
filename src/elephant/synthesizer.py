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

from elephant.atlas.atlas import STAGE_LABELS, STAGES, Atlas

# LLM_PROVIDER: "anthropic" (default) or "openai"
# LLM_MODEL: override the default model for the chosen provider
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai").lower()
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
    def __init__(self, data_dir: str, tickers_file: str, atlas: Optional[Atlas] = None):
        self.data_dir = data_dir
        self.tickers_file = tickers_file
        self.atlas = atlas
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

    def _load_names(self, tickers: list[str]) -> dict[str, str]:
        import json
        from concurrent.futures import ThreadPoolExecutor
        cache_path = os.path.join(self.data_dir, "ticker_names.json")
        try:
            cache = json.loads(open(cache_path).read()) if os.path.exists(cache_path) else {}
        except Exception:
            cache = {}

        missing = [t for t in tickers if t not in cache]
        if missing:
            def fetch(ticker):
                try:
                    import yfinance as yf
                    info = yf.Ticker(ticker).info
                    return ticker, info.get("shortName") or info.get("longName") or ticker
                except Exception:
                    return ticker, ticker

            with ThreadPoolExecutor(max_workers=8) as ex:
                for ticker, name in ex.map(fetch, missing):
                    cache[ticker] = name

            try:
                with open(cache_path, "w") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
            except Exception:
                logging.exception("Failed to save ticker_names.json")

        return cache

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
        candidates: list[dict],
        minkabu: dict[str, str],
        tdnet: list[dict],
    ) -> str:
        lines = [f"Today: {datetime.now().strftime('%Y-%m-%d')}", ""]

        def fmt(c: dict) -> str:
            name   = f" ({c['name']})" if c.get("name") else ""
            value_chain  = f" [{c['value_chain_id']}/{c['stage']}]" if c.get("value_chain_id") else ""
            laggard = f" lag {c['laggard_gap_1y']:+.1f}% vs stage" if c.get("laggard_gap_1y") is not None else ""
            bull   = f" bull {c['bull_pct']:.0f}%" if c.get("bull_pct") is not None else ""
            bear   = f" bear {c['bear_pct']:.0f}%" if c.get("bear_pct") is not None else ""
            ret1m  = f" {c['return_1m']:+.1f}% 1m" if c.get("return_1m") is not None else ""
            speed  = ""
            if c.get("speed_latest") is not None:
                speed = f" speed {c['speed_latest']:.1f}"
                if c.get("speed_prev") is not None:
                    speed += f"→{c['speed_prev']:.1f} c/h"
                if c.get("speed_trend") == "accel":
                    speed += " ↑"
            rank   = f" BBS#{c['bbs_rank']}" if c.get("bbs_rank") and c.get("bbs_today") else ""
            tdnet_flag = " [TDnet]" if c.get("has_tdnet_48h") else ""
            mink_flag  = " [Minkabu]" if c.get("has_minkabu") else ""
            score  = f" score:{c['score']}"
            return f"  {c['ticker']}{name}{value_chain}{laggard}{bull}{bear}{ret1m}{speed}{rank}{tdnet_flag}{mink_flag}{score}"

        # Queue A: Value Chain Candidates
        qa = [c for c in candidates if c["queue"] == "A"]
        if qa:
            lines.append("## Queue A — Value Chain Candidates (confirmed theme, not yet re-rated)")
            lines.append("These tickers fit a known thematic wave but have not caught up with stage peers.")
            lines.append("")
            for c in qa[:20]:
                lines.append(fmt(c))
                lines.append(f"    reason: {c['queue_reason']}")

        # Queue B: Holding Signals
        qb = [c for c in candidates if c["queue"] == "B"]
        if qb:
            lines.append("")
            lines.append("## Queue B — Holding Signals (price down, thesis intact)")
            lines.append("Price has fallen recently but sentiment remains bullish. Worth checking if thesis still holds.")
            lines.append("")
            for c in qb[:10]:
                lines.append(fmt(c))
                lines.append(f"    reason: {c['queue_reason']}")

        # Queue C: Crowd Heat / Noise
        qc = [c for c in candidates if c["queue"] == "C"]
        if qc:
            lines.append("")
            lines.append("## Queue C — Crowd Heat / Noise (no confirmed value_chain fit)")
            lines.append("High BBS activity but no confirmed thematic value_chain fit. Surface for awareness only.")
            lines.append("")
            for c in qc[:15]:
                lines.append(fmt(c))

        if tdnet:
            lines.append("")
            lines.append("## 適時開示（TDnet）— 直近48h")
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
        lines.append("Sources: Google News (JP economy, semiconductors, AI infrastructure, robotics, pharma)")
        lines.append("")
        for item in news[:60]:
            source = item.get("source", "")
            title = item.get("title", "")
            summary = (item.get("summary") or "")[:200]
            lines.append(f"- [{source}] {title}")
            if summary:
                lines.append(f"  {summary}")
        if self.atlas:
            lines.append("")
            lines.append("## Current Atlas (known instruments)")
            lines.append("Use this to identify thin/empty stages for RIVER GAP hints.")
            for value_chain in self.atlas.list_value_chains():
                by_stage = {stage: [] for stage in STAGES}
                for company in value_chain.companies:
                    if company.stage in by_stage:
                        by_stage[company.stage].append(company.ticker)
                stage_parts = []
                for stage in STAGES:
                    t = by_stage[stage]
                    stage_parts.append(f"{stage}: {', '.join(t) if t else '(empty)'}")
                lines.append(f"  {value_chain.name}: {' | '.join(stage_parts)}")
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
        from elephant.candidates import CandidateMetrics
        since = datetime.now() - timedelta(hours=48)

        atlas_path = os.path.join(self.data_dir, "atlas.json") if self.atlas else None
        candidates = CandidateMetrics(self.data_dir, self.tickers_file, atlas_path=atlas_path).build()

        if not candidates:
            return "No tickers found. Run `python src/cli.py fetch --dataset yjp_bbs_rank` first."

        # Minkabu text is still passed to the LLM for narrative richness
        all_tickers = [c["ticker"] for c in candidates]
        minkabu = self._load_minkabu(all_tickers, since)
        news = self._load_news(since)
        tdnet = self._load_tdnet(all_tickers, since)
        names = self._load_names(all_tickers[:40])
        # Back-fill names into candidates that didn't have them cached
        for c in candidates:
            if not c.get("name") and names.get(c["ticker"]):
                c["name"] = names[c["ticker"]]

        date_str = datetime.now().strftime("%Y-%m-%d")

        value_chain_context = ""
        if self.atlas and self.atlas.list_value_chains():
            value_chain_context = "\nKnown value_chains: " + ", ".join(r.name for r in self.atlas.list_value_chains())
            value_chain_context += "\nStages: source → prime → bottleneck (highest alpha) → capacity"

        # --- Call 1: Japanese hints from BBS + Minkabu ---
        jp_system = f"""\
あなたは自己投資家向けのデイリーダイジェストを書く金融リサーチスカウトです。

投資家の戦略：テーマ波（確認済みリバー）の中で、まだ市場に再評価されていない銘柄を探す。
保有期間は数週間〜数ヶ月。ヒントは調査のきっかけであり、売買シグナルではない。{value_chain_context}

入力データはすでに3つのキューに分類されています：
- Queue A: リバー適合 + レイヤー平均比で出遅れ → 最優先で調査価値あり
- Queue B: 株価下落中だが強気センチメント維持 → テーゼ継続確認
- Queue C: BBS熱量あり、リバー適合なし → 注目のみ、調査優先度は低い

## 出力フォーマット

Queue A から最大2件、Queue B から最大1件、Queue C から最大1件を選び、以下の形式で書いてください：

- [RIVER CANDIDATE]: Queue Aの銘柄。なぜこの銘柄がリバーに適合し、なぜ出遅れているか説明する。
- [HOLDING SIGNAL]: Queue Bの銘柄。株価下落にもかかわらず強気センチメントが維持されている理由を説明する。
- [CROWD HEAT]: Queue Cの銘柄。BBS熱量の理由を説明し、リバー適合がない旨を明記する。

各ヒント：3〜5行。「→ 調査の価値あり」または「→ 確認の価値あり」で締めること。
トリガーとなったシグナル（スコア、出遅れ幅、BBS速度、TDnet、Minkabuなど）を必ず明記すること。
TDnet開示がある銘柄は、開示内容がセンチメントと一致・相反どちらかを確認すること。
トーン：意見ははっきりと、でも謙虚に。ヘッダー行（=== Elephant...）は出力しないこと。\
"""

        # --- Call 2: English hints from news + atlas ---
        en_system = f"""\
You are a financial research scout writing part of a Daily Digest for a self-directed investor.
The investor holds positions for weeks to months and does their own research after reading the digest.{value_chain_context}

Write 2 to 3 hints in English based ONLY on the news headlines and atlas below.
Use these hint types:
- [RIVER GAP]: a stage in a known value_chain that is empty or thin — suggest what type of instrument to look for
- [MACRO OBSERVATION]: a macro, currency, or geopolitical angle worth watching
- [SECTOR THEME]: a theme emerging from multiple news items pointing at the same supply chain stage

Each hint: 3 to 5 lines. End with "→ Worth looking at..." or "→ Worth checking..."
State which news items or value_chain gap triggered the hint.
Do not suggest tickers already in the atlas.
Tone: opinionated but humble.
Do NOT output a header line (no === Elephant Digest... line).\
"""

        jp_hints = self._llm(jp_system, self._build_jp_context(candidates, minkabu, tdnet))
        en_hints = self._llm(en_system, self._build_en_context(news))

        return (
            f"=== Elephant Digest · {date_str} ===\n\n"
            f"{jp_hints.strip()}\n\n"
            f"---\n\n"
            f"{en_hints.strip()}"
        )
