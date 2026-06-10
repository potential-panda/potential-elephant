"""
Candidate metrics builder.

Joins BBS heat + sentiment + river fit + laggard gap + catalyst into one
deterministic table. The synthesizer uses this table instead of raw BBS data
so the LLM receives pre-ranked, queue-split candidates rather than noise.

Queue definitions:
  A — River Candidate: in a confirmed river AND lagging peers, or in a river
      with active BBS heat. Deserves research time.
  B — Holding Signal: monitored ticker, price down recently but sentiment
      still intact. Worth checking whether thesis holds.
  C — Crowd Heat / Noise: high BBS activity but no confirmed river fit.
      Surface for awareness, not for research priority.
"""

import glob
import json
import logging
import math
import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd


def _pct_change(df: pd.DataFrame, days: int) -> Optional[float]:
    if df.empty:
        return None
    latest_date = df["date"].max()
    cutoff = latest_date - timedelta(days=days)
    window = df[df["date"] <= cutoff + timedelta(days=7)]
    if window.empty:
        return None
    start_close = float(window.iloc[-1]["close"])
    end_close = float(df.iloc[-1]["close"])
    if start_close == 0:
        return None
    result = (end_close - start_close) / start_close * 100
    return round(result, 2) if math.isfinite(result) else None


class CandidateMetrics:
    def __init__(self, data_dir: str, tickers_file: str, tree_path: Optional[str] = None):
        self.data_dir = data_dir
        self.tickers_file = tickers_file
        self.tree_path = tree_path

    # ── loaders ───────────────────────────────────────────────────────────────

    def _load_bbs_tickers(self) -> list[str]:
        """Tickers from tickers.txt — order = BBS rank (today's ranked first)."""
        if not os.path.exists(self.tickers_file):
            return []
        with open(self.tickers_file) as f:
            return [line.strip() for line in f if line.strip()]

    def _load_bbs_signals(self, tickers: list[str]) -> dict[str, dict]:
        """
        {ticker: {rank, is_today, speed_latest, speed_prev, trend}}
        rank = 1-indexed position in tickers.txt
        is_today = ticker appeared in today's BBS rank scrape
        """
        from elephant.ticker_registry import load_cache
        cache = load_cache(self.tickers_file)
        today = datetime.now().date().isoformat()
        week_ago = (datetime.now() - timedelta(days=7)).date().isoformat()

        result = {}
        for i, ticker in enumerate(tickers, 1):
            entry = cache.get(ticker)
            if not isinstance(entry, dict):
                result[ticker] = {"rank": i, "is_today": False}
                continue

            history = [
                h for h in entry.get("speed_history", [])
                if h.get("date", "") >= week_ago
            ]
            speeds = [h["comments_per_hour"] for h in history[:3]]
            speed_latest = speeds[0] if speeds else None
            speed_prev = speeds[1] if len(speeds) > 1 else None

            trend = None
            if speed_latest is not None and speed_prev is not None and speed_prev > 0:
                ratio = speed_latest / speed_prev
                if ratio >= 1.3:
                    trend = "accel"
                elif ratio <= 0.7:
                    trend = "decel"
                else:
                    trend = "stable"

            result[ticker] = {
                "rank": i,
                "is_today": entry.get("last_seen", "") == today,
                "speed_latest": speed_latest,
                "speed_prev": speed_prev,
                "trend": trend,
            }
        return result

    def _load_sentiment(self, tickers: list[str]) -> dict[str, dict]:
        """
        {ticker: {strongest, strong, both, weak, weakest, bull_pct, bear_pct, scraped_at}}
        All five fields are guaranteed to be floats (0.0 if missing).
        """
        result = {}
        year = datetime.now().strftime("%Y")
        since = datetime.now() - timedelta(days=7)

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
                row = recent.iloc[-1]
                strongest = float(row.get("strongest") or 0)
                strong    = float(row.get("strong")    or 0)
                both      = float(row.get("both")      or 0)
                weak      = float(row.get("weak")      or 0)
                weakest   = float(row.get("weakest")   or 0)
                result[ticker] = {
                    "strongest":  strongest,
                    "strong":     strong,
                    "both":       both,
                    "weak":       weak,
                    "weakest":    weakest,
                    "bull_pct":   round(strongest + strong, 1),
                    "bear_pct":   round(weak + weakest, 1),
                    "scraped_at": str(row["scraped_at"])[:19],
                }
            except Exception:
                logging.exception(f"[candidates] sentiment load failed: {ticker}")
        return result

    def _load_price_changes(self, ticker: str) -> dict:
        path = os.path.join(
            self.data_dir, "dataset=daily_prices", f"ticker={ticker}", "data.parquet"
        )
        if not os.path.exists(path):
            return {}
        try:
            df = pd.read_parquet(path)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            return {
                "1y": _pct_change(df, 365),
                "6m": _pct_change(df, 180),
                "3m": _pct_change(df, 90),
                "1m": _pct_change(df, 30),
                "last_date": df.iloc[-1]["date"].strftime("%Y-%m-%d") if not df.empty else None,
            }
        except Exception:
            return {}

    def _load_river_tree(self) -> dict[str, dict]:
        """
        {ticker: {river_id, river_name, layer}}
        First occurrence wins when a ticker appears in multiple rivers.
        """
        if not self.tree_path or not os.path.exists(self.tree_path):
            return {}
        with open(self.tree_path, encoding="utf-8") as f:
            data = json.load(f)
        result = {}
        for river in data.get("rivers", []):
            for node in river.get("nodes", []):
                t = node["ticker"]
                if t not in result:
                    result[t] = {
                        "river_id":   river["id"],
                        "river_name": river["name"],
                        "layer":      node["layer"],
                    }
        return result

    def _compute_layer_avgs(
        self, all_prices: dict[str, dict]
    ) -> dict[tuple, dict]:
        """
        {(river_id, layer): {avg_1y, avg_6m, avg_3m, avg_1m}}
        Uses all nodes in the tree for computing the average.
        """
        if not self.tree_path or not os.path.exists(self.tree_path):
            return {}
        with open(self.tree_path, encoding="utf-8") as f:
            data = json.load(f)

        groups: dict[tuple, list[str]] = {}
        for river in data.get("rivers", []):
            for node in river.get("nodes", []):
                key = (river["id"], node["layer"])
                groups.setdefault(key, []).append(node["ticker"])

        result = {}
        for key, tickers_in_layer in groups.items():
            avgs = {}
            for period in ("1y", "6m", "3m", "1m"):
                vals = [
                    all_prices[t][period]
                    for t in tickers_in_layer
                    if t in all_prices
                    and all_prices[t].get(period) is not None
                    and math.isfinite(all_prices[t][period])
                ]
                avgs[f"avg_{period}"] = round(sum(vals) / len(vals), 2) if vals else None
            result[key] = avgs
        return result

    def _load_tdnet_48h(self) -> set[str]:
        pattern = os.path.join(
            self.data_dir, "dataset=tdnet_disclosures", "date=*", "data.parquet"
        )
        since = datetime.now() - timedelta(hours=48)
        tickers: set[str] = set()
        for f in glob.glob(pattern):
            try:
                df = pd.read_parquet(f)
                df["scraped_at"] = pd.to_datetime(df["scraped_at"])
                for t in df[df["scraped_at"] >= since]["ticker"].dropna().unique():
                    tickers.add(str(t))
            except Exception:
                pass
        return tickers

    def _load_minkabu_available(self, tickers: list[str]) -> set[str]:
        year = datetime.now().strftime("%Y")
        since = datetime.now() - timedelta(days=7)
        available: set[str] = set()
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
                if not df[df["scraped_at"] >= since].empty:
                    available.add(ticker)
            except Exception:
                pass
        return available

    def _load_names(self, tickers: list[str]) -> dict[str, str]:
        cache_path = os.path.join(self.data_dir, "ticker_names.json")
        try:
            cache = json.loads(open(cache_path).read()) if os.path.exists(cache_path) else {}
        except Exception:
            cache = {}
        return {t: cache.get(t, "") for t in tickers}

    # ── scoring ───────────────────────────────────────────────────────────────

    @staticmethod
    def _score(
        bbs_rank: Optional[int],
        is_today_bbs: bool,
        speed_trend: Optional[str],
        bull_pct: Optional[float],
        return_1m: Optional[float],
        river_id: Optional[str],
        laggard_gap: Optional[float],
        has_tdnet: bool,
        has_minkabu: bool,
    ) -> tuple[int, str, str]:
        """Returns (score 0-100, queue 'A'/'B'/'C', human-readable reason)."""
        score = 0

        # River fit — max 35 pts
        if river_id:
            score += 20
            if laggard_gap is not None:
                if laggard_gap <= -20:   score += 15
                elif laggard_gap <= -10: score += 10
                elif laggard_gap <= -5:  score += 5

        # BBS heat — max 25 pts
        if bbs_rank is not None and is_today_bbs:
            score += max(0, 20 - bbs_rank)
        if speed_trend == "accel":  score += 10
        elif speed_trend == "stable": score += 3

        # Sentiment quality — max 20 pts
        if bull_pct is not None:
            if bull_pct > 70:   score += 20
            elif bull_pct > 55: score += 12
            elif bull_pct > 40: score += 6

        # Catalyst — max 15 pts
        if has_tdnet:   score += 10
        if has_minkabu: score += 5

        score = min(score, 100)

        # Queue assignment
        if river_id and laggard_gap is not None and laggard_gap <= -10:
            queue = "A"
            reason = f"river:{river_id} laggard {laggard_gap:+.1f}% vs layer avg"
        elif river_id and is_today_bbs and bbs_rank is not None and bbs_rank <= 30:
            queue = "A"
            reason = f"river:{river_id} BBS rank {bbs_rank} today"
        elif return_1m is not None and return_1m < -5 and bull_pct is not None and bull_pct > 60:
            queue = "B"
            reason = f"price {return_1m:+.1f}% 1m · bull {bull_pct:.0f}%"
        else:
            queue = "C"
            reason = "crowd heat · no confirmed river fit"

        return score, queue, reason

    # ── main ──────────────────────────────────────────────────────────────────

    def build(self) -> list[dict]:
        """
        Build and return candidate metrics table sorted by score desc.

        Covers:
          - All tickers from tickers.txt (BBS ranked + recently retained)
          - All JP tickers from the river tree that aren't already in tickers.txt
            (for laggard detection even when not BBS-hot)
        """
        bbs_tickers = self._load_bbs_tickers()

        # Add river tree JP tickers not already in BBS list
        river_nodes = self._load_river_tree()
        tree_jp = [t for t in river_nodes if t.endswith(".T") and t not in bbs_tickers]
        all_tickers = bbs_tickers + tree_jp

        if not all_tickers:
            return []

        bbs     = self._load_bbs_signals(bbs_tickers)   # rank only meaningful for bbs_tickers
        senti   = self._load_sentiment(all_tickers)
        tdnet   = self._load_tdnet_48h()
        minkabu = self._load_minkabu_available(all_tickers)
        names   = self._load_names(all_tickers)

        # Load prices for all tickers (including US tree nodes for layer avg computation)
        all_tree_tickers = list(river_nodes.keys())
        price_tickers = list(dict.fromkeys(all_tickers + all_tree_tickers))
        all_prices = {t: self._load_price_changes(t) for t in price_tickers}

        layer_avgs = self._compute_layer_avgs(all_prices)

        rows = []
        for ticker in all_tickers:
            b  = bbs.get(ticker, {})
            s  = senti.get(ticker, {})
            p  = all_prices.get(ticker, {})
            rf = river_nodes.get(ticker)

            bull_pct = s.get("bull_pct")
            bear_pct = s.get("bear_pct")

            layer_avg_1y = None
            laggard_gap  = None
            if rf:
                key = (rf["river_id"], rf["layer"])
                la = layer_avgs.get(key, {})
                layer_avg_1y = la.get("avg_1y")
                if layer_avg_1y is not None and p.get("1y") is not None:
                    laggard_gap = round(p["1y"] - layer_avg_1y, 2)

            is_today = b.get("is_today", False)
            score, queue, reason = self._score(
                bbs_rank     = b.get("rank") if ticker in bbs else None,
                is_today_bbs = is_today,
                speed_trend  = b.get("trend"),
                bull_pct     = bull_pct,
                return_1m    = p.get("1m"),
                river_id     = rf["river_id"] if rf else None,
                laggard_gap  = laggard_gap,
                has_tdnet    = ticker in tdnet,
                has_minkabu  = ticker in minkabu,
            )

            rows.append({
                "ticker":        ticker,
                "name":          names.get(ticker, ""),
                "market":        "JP" if ticker.endswith(".T") else "US",
                # BBS
                "bbs_rank":      b.get("rank") if ticker in bbs else None,
                "bbs_today":     is_today,
                "speed_latest":  b.get("speed_latest"),
                "speed_prev":    b.get("speed_prev"),
                "speed_trend":   b.get("trend"),
                # Sentiment
                "bull_pct":      bull_pct,
                "bear_pct":      bear_pct,
                "eval_scraped_at": s.get("scraped_at"),
                # River fit
                "river_id":      rf["river_id"]   if rf else None,
                "river_name":    rf["river_name"] if rf else None,
                "layer":         rf["layer"]       if rf else None,
                # Price / laggard
                "return_1y":     p.get("1y"),
                "return_6m":     p.get("6m"),
                "return_3m":     p.get("3m"),
                "return_1m":     p.get("1m"),
                "price_date":    p.get("last_date"),
                "layer_avg_1y":  layer_avg_1y,
                "laggard_gap_1y": laggard_gap,
                # Catalyst
                "has_tdnet_48h": ticker in tdnet,
                "has_minkabu":   ticker in minkabu,
                # Score
                "score":         score,
                "queue":         queue,
                "queue_reason":  reason,
            })

        # Apply suppression penalty — suppressed "pass" tickers get score capped at 5
        # and are moved to queue C so they don't consume attention
        try:
            from elephant.decisions import is_suppressed, get as get_decision
            for row in rows:
                t = row["ticker"]
                if is_suppressed(t):
                    row["score"] = min(row["score"], 5)
                    row["queue"] = "C"
                    dec = get_decision(t)
                    row["queue_reason"] = f"suppressed until {dec['suppress_until']}: {dec.get('reason','')}"
                    row["suppressed"] = True
                else:
                    row["suppressed"] = False
        except Exception:
            for row in rows:
                row.setdefault("suppressed", False)

        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows
