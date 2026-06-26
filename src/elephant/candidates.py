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


def _high_28d(df: pd.DataFrame) -> Optional[float]:
    """Maximum daily close over the past 28 calendar days."""
    if df.empty:
        return None
    latest_date = df["date"].max()
    cutoff = latest_date - timedelta(days=28)
    window = df[df["date"] >= cutoff]
    if window.empty:
        return None
    return round(float(window["close"].max()), 4)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


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

    def _load_bbs_signals(self, all_tickers: list[str], bbs_tickers: list[str]) -> dict[str, dict]:
        """
        {ticker: {rank, is_today, speed_latest, speed_prev, trend, has_yahoo_jp_bbs}}
        rank = 1-indexed BBS position (only meaningful for tickers in bbs_tickers)
        has_yahoo_jp_bbs = True/False/None (None = not yet probed, only set for US tickers)
        """
        from elephant.ticker_registry import get_yahoo_jp_bbs_status, load_cache

        cache = load_cache(self.tickers_file)
        today = datetime.now().date().isoformat()
        week_ago = (datetime.now() - timedelta(days=7)).date().isoformat()
        bbs_rank = {t: i for i, t in enumerate(bbs_tickers, 1)}

        result = {}
        for ticker in all_tickers:
            entry = cache.get(ticker)
            rank = bbs_rank.get(ticker)
            bbs_status = get_yahoo_jp_bbs_status(cache, ticker)

            if not isinstance(entry, dict):
                result[ticker] = {
                    "rank": rank,
                    "is_today": False,
                    "speed_latest": None,
                    "speed_prev": None,
                    "trend": None,
                    "has_yahoo_jp_bbs": bbs_status,
                    "speed_history_recent": [],
                }
                continue

            history = [h for h in entry.get("speed_history", []) if h.get("date", "") >= week_ago]
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
                "rank": rank,
                "is_today": entry.get("last_seen", "") == today,
                "speed_latest": speed_latest,
                "speed_prev": speed_prev,
                "trend": trend,
                "has_yahoo_jp_bbs": bbs_status,
                "speed_history_recent": speeds,
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
                self.data_dir,
                "dataset=yahoo_evaluations",
                f"ticker={ticker}",
                f"YEAR={year}",
                "data.parquet",
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
                strongest = _safe_float(row.get("strongest"))
                strong = _safe_float(row.get("strong"))
                both = _safe_float(row.get("both"))
                weak = _safe_float(row.get("weak"))
                weakest = _safe_float(row.get("weakest"))
                result[ticker] = {
                    "strongest": strongest,
                    "strong": strong,
                    "both": both,
                    "weak": weak,
                    "weakest": weakest,
                    "bull_pct": round(strongest + strong, 1),
                    "bear_pct": round(weak + weakest, 1),
                    "scraped_at": str(row["scraped_at"])[:19],
                }
            except Exception:
                logging.exception(f"[candidates] sentiment load failed: {ticker}")
        return result

    def _load_price_changes(self, ticker: str) -> dict:
        path = os.path.join(self.data_dir, "dataset=daily_prices", f"ticker={ticker}", "data.parquet")
        if not os.path.exists(path):
            return {}
        try:
            df = pd.read_parquet(path)
            df["date"] = pd.to_datetime(df["date"])
            df = df.dropna(subset=["close"]).sort_values("date")
            last_row = df.iloc[-1] if not df.empty else None
            return {
                "1y": _pct_change(df, 365),
                "6m": _pct_change(df, 180),
                "3m": _pct_change(df, 90),
                "1m": _pct_change(df, 30),
                "4w": _pct_change(df, 28),
                "12w": _pct_change(df, 84),
                "high_28d": _high_28d(df),
                "last_close": round(float(last_row["close"]), 4) if last_row is not None else None,
                "last_date": last_row["date"].strftime("%Y-%m-%d") if last_row is not None else None,
            }
        except Exception:
            return {}

    def _load_river_tree(self) -> dict[str, dict]:
        """
        {ticker: {river_id, river_name, layer, status, primary_river}}
        First occurrence wins when a ticker appears in multiple rivers.
        Dormant/rejected nodes are preserved in the tree but excluded from daily
        candidate scoring.
        """
        if not self.tree_path or not os.path.exists(self.tree_path):
            return {}
        with open(self.tree_path, encoding="utf-8") as f:
            data = json.load(f)
        result = {}
        for river in data.get("rivers", []):
            for node in river.get("nodes", []):
                status = node.get("status", "active")
                if status in {"dormant", "rejected"}:
                    continue
                t = node["ticker"]
                if t not in result:
                    result[t] = {
                        "river_id": river["id"],
                        "river_name": river["name"],
                        "layer": node["layer"],
                        "status": status,
                        "primary_river": node.get("primary_river", True),
                    }
        return result

    def _compute_layer_avgs(self, all_prices: dict[str, dict]) -> dict[tuple, dict]:
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
                node_status = node.get("status", "active")
                if node_status in ("active", "weak"):
                    key = (river["id"], node["layer"])
                    groups.setdefault(key, []).append(node["ticker"])

        result = {}
        for key, tickers_in_layer in groups.items():
            avgs = {}
            for period in ("1y", "6m", "3m", "1m", "4w", "12w"):
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

    def _load_tdnet_48h(self) -> dict[str, list[dict]]:
        pattern = os.path.join(self.data_dir, "dataset=tdnet_disclosures", "date=*", "data.parquet")
        since = datetime.now() - timedelta(hours=48)
        result: dict[str, list[dict]] = {}
        for f in glob.glob(pattern):
            try:
                df = pd.read_parquet(f)
                df["scraped_at"] = pd.to_datetime(df["scraped_at"])
                recent = df[df["scraped_at"] >= since]
                for _, row in recent.dropna(subset=["ticker"]).iterrows():
                    t = str(row["ticker"])
                    item = {
                        "title": str(row.get("title", "") or ""),
                        "date": str(row.get("date", "") or ""),
                        "url": str(row.get("url", "") or ""),
                        "id": str(row.get("id", "") or ""),
                    }
                    result.setdefault(t, []).append(item)
            except Exception:
                pass
        return result

    def _load_minkabu_available(self, tickers: list[str]) -> dict[str, Optional[datetime]]:
        year = datetime.now().strftime("%Y")
        since = datetime.now() - timedelta(days=7)
        available: dict[str, Optional[datetime]] = {}
        for ticker in tickers:
            path = os.path.join(
                self.data_dir,
                "dataset=minkabu_raw_html",
                f"ticker={ticker}",
                f"YEAR={year}",
                "data.parquet",
            )
            if not os.path.exists(path):
                continue
            try:
                df = pd.read_parquet(path)
                df["scraped_at"] = pd.to_datetime(df["scraped_at"])
                recent = df[df["scraped_at"] >= since]
                if not recent.empty:
                    latest_scraped_at = recent["scraped_at"].max()
                    available[ticker] = latest_scraped_at.to_pydatetime()
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
    def _score_legacy(
        is_jp: bool,
        bbs_rank: Optional[int],
        is_today_bbs: bool,
        speed_trend: Optional[str],
        speed_latest: Optional[float],
        has_yahoo_jp_bbs: Optional[bool],
        bull_pct: Optional[float],
        return_1m: Optional[float],
        return_1y: Optional[float],
        river_id: Optional[str],
        laggard_gap: Optional[float],
        has_tdnet: bool,
        has_minkabu: bool,
    ) -> tuple[int, str, str]:
        """Returns (score 0-100, queue 'A'/'B'/'C', human-readable reason).

        Score structure (max 100):
          River fit    40 pts  — presence(15) + gap scale(up to 20) + true-laggard bonus(5)
          Market heat  35 pts  — JP: BBS rank/speed/Minkabu; US: BBS presence/momentum
          Sentiment    15 pts  — Yahoo JP bull% (JP-only currently)
          Catalyst     10 pts  — TDnet (JP) / Minkabu (JP)

        Laggard gap tiers (vs layer 1y avg):
          -100%+ → +20   -50%+ → +16   -20%+ → +12   -10%+ → +7   -5%+ → +3
        True laggard bonus (+5): gap ≤ -30% AND 1y return < 15%
          (stock hasn't moved in absolute terms either — best catch-up candidate)
        """
        score = 0

        # ── River fit (max 40) ────────────────────────────────────────────────
        if river_id:
            score += 15
            if laggard_gap is not None:
                if laggard_gap <= -100:
                    score += 20
                elif laggard_gap <= -50:
                    score += 16
                elif laggard_gap <= -20:
                    score += 12
                elif laggard_gap <= -10:
                    score += 7
                elif laggard_gap <= -5:
                    score += 3
            # "True laggard" bonus: still sleeping in absolute terms too
            if laggard_gap is not None and laggard_gap <= -30 and return_1y is not None and return_1y < 15:
                score += 5

        # ── Market heat (max 35) ─────────────────────────────────────────────
        if is_jp:
            # JP: sourced from BBS ranking list — silence is confirmed inactivity
            has_any_bbs = speed_latest is not None or bbs_rank is not None
            if has_any_bbs:
                if bbs_rank is not None and is_today_bbs:
                    score += max(0, 20 - bbs_rank)  # rank 1 → +19, rank 10 → +10
                if speed_trend == "accel":
                    score += 8
                elif speed_trend == "stable":
                    score += 3
                if has_minkabu:
                    score += 5
            else:
                score -= 10  # JP in tree but never appeared in BBS — confirmed quiet
        else:
            # US: BBS coverage is rare — presence is a strong signal
            if speed_latest is not None:
                # Has Yahoo JP BBS comments — big bonus
                score += 15
                if speed_trend == "accel":
                    score += 8
                elif speed_trend == "stable":
                    score += 3
            elif has_yahoo_jp_bbs is False:
                # Confirmed no BBS page — small penalty
                score -= 3
            else:
                # Not yet probed or unknown — small penalty
                score -= 3

            # Price momentum as proxy for US market heat
            if return_1m is not None:
                if return_1m > 30:
                    score += 20
                elif return_1m > 15:
                    score += 12
                elif return_1m > 5:
                    score += 6
                elif return_1m < -10:
                    score -= 5

        # ── Sentiment (max 15) ───────────────────────────────────────────────
        if bull_pct is not None:
            if bull_pct > 70:
                score += 15
            elif bull_pct > 55:
                score += 9
            elif bull_pct > 40:
                score += 5

        # ── Catalyst (max 10) ────────────────────────────────────────────────
        if has_tdnet:
            score += 7
        if has_minkabu and not is_jp:
            score += 3  # Minkabu already counted in JP heat

        score = min(score, 100)

        # ── Queue assignment ─────────────────────────────────────────────────
        if river_id and laggard_gap is not None and laggard_gap <= -10:
            queue = "A"
            reason = f"river:{river_id} laggard {laggard_gap:+.1f}% vs layer avg"
        elif river_id and is_today_bbs and bbs_rank is not None and bbs_rank <= 30:
            queue = "A"
            reason = f"river:{river_id} BBS rank {bbs_rank} today"
        elif river_id and not is_jp and return_1m is not None and return_1m > 15:
            queue = "A"
            reason = f"river:{river_id} US momentum {return_1m:+.1f}% 1m"
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
        import json as _json

        from elephant.scoring import (
            score_d1, score_d2, score_d3, score_d4, score_d5, score_d6,
            compute_noise_penalty, compute_decision_memory_adjustment, compute_final_score,
            _classify_tdnet_title,
        )
        from elephant.decisions import get as get_decision_entry, is_suppressed

        bbs_tickers = self._load_bbs_tickers()

        # Add all river tree tickers (JP and US) not already in BBS list
        river_nodes = self._load_river_tree()
        tree_extra = [t for t in river_nodes if t not in bbs_tickers]
        all_tickers = bbs_tickers + tree_extra

        if not all_tickers:
            return []

        bbs = self._load_bbs_signals(all_tickers, bbs_tickers)
        senti = self._load_sentiment(all_tickers)
        tdnet = self._load_tdnet_48h()
        minkabu = self._load_minkabu_available(all_tickers)
        names = self._load_names(all_tickers)

        # Load prices for all tickers (including US tree nodes for layer avg computation)
        all_tree_tickers = list(river_nodes.keys())
        price_tickers = list(dict.fromkeys(all_tickers + all_tree_tickers))
        all_prices = {t: self._load_price_changes(t) for t in price_tickers}

        layer_avgs = self._compute_layer_avgs(all_prices)

        # Load tree data once for D2 peer computation (avoid re-reading per ticker)
        tree_data_global = {}
        if self.tree_path and os.path.exists(self.tree_path):
            with open(self.tree_path, encoding="utf-8") as f:
                tree_data_global = _json.load(f)

        # Load BBS cache once for D5 rank history
        from elephant.ticker_registry import load_cache
        bbs_cache = load_cache(self.tickers_file)

        rows = []
        for ticker in all_tickers:
            b = bbs.get(ticker, {})
            s = senti.get(ticker, {})
            p = all_prices.get(ticker, {})
            rf = river_nodes.get(ticker)

            bull_pct = s.get("bull_pct")
            bear_pct = s.get("bear_pct")

            layer_avg_1y = None
            laggard_gap = None
            if rf:
                key = (rf["river_id"], rf["layer"])
                la = layer_avgs.get(key, {})
                layer_avg_1y = la.get("avg_1y")
                if layer_avg_1y is not None and p.get("1y") is not None:
                    laggard_gap = round(p["1y"] - layer_avg_1y, 2)

            is_today = b.get("is_today", False)
            is_jp = ticker.endswith(".T")
            _legacy_score, _legacy_queue, reason = self._score_legacy(
                is_jp=is_jp,
                bbs_rank=b.get("rank"),
                is_today_bbs=is_today,
                speed_trend=b.get("trend"),
                speed_latest=b.get("speed_latest"),
                has_yahoo_jp_bbs=b.get("has_yahoo_jp_bbs"),
                bull_pct=bull_pct,
                return_1m=p.get("1m"),
                return_1y=p.get("1y"),
                river_id=rf["river_id"] if rf else None,
                laggard_gap=laggard_gap,
                has_tdnet=bool(tdnet.get(ticker)),
                has_minkabu=ticker in minkabu,
            )

            # ── D1-D6 new scoring ─────────────────────────────────────────────

            # Build evidence items from available data
            evidence_items = []

            # TDnet items
            tdnet_items = tdnet.get(ticker, [])
            for disclosure in tdnet_items:
                title = disclosure.get("title", "")
                raw_pts = _classify_tdnet_title(title)
                date_str = disclosure.get("date", "") or datetime.now().strftime("%Y-%m-%d")
                try:
                    days_old = (datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")).days
                except ValueError:
                    days_old = 0
                evidence_items.append({
                    "role": "catalyst",
                    "source": "TDnet",
                    "source_tier": 2,
                    "raw_points": raw_pts,
                    "freshness_days": max(0, days_old),
                    "deduplication_id": f"tdnet:{disclosure.get('id', title[:20])}",
                    "title": title,
                })

            # Minkabu
            minkabu_scraped_at = minkabu.get(ticker) if isinstance(minkabu, dict) else None
            has_minkabu = (
                minkabu_scraped_at is not None
                and (datetime.now() - minkabu_scraped_at).days <= 90
            )

            # BBS rank history from cache (newest first)
            ticker_cache = bbs_cache.get(ticker, {})
            speed_history = ticker_cache.get("speed_history", []) if isinstance(ticker_cache, dict) else []
            bbs_rank_history = sorted(
                [h for h in speed_history if "rank" in h],
                key=lambda h: h.get("date", ""),
                reverse=True,
            )

            # D1
            node_status = rf.get("status", "active") if rf else None
            has_keyword_routing = bool(tdnet_items) and not rf
            d1 = score_d1(
                node_status=node_status,
                is_primary_river=rf.get("primary_river", True) if rf else False,
                has_proposed_evidence=bool(tdnet_items) if node_status == "proposed" else False,
                has_minkabu_theme=has_minkabu and not rf,
                has_keyword_routing=has_keyword_routing,
            )

            # D2 — peer 4w returns and active/weak node count from pre-loaded tree data
            peer_4w_returns = []
            active_weak_count = 0
            if rf:
                for river_d2 in tree_data_global.get("rivers", []):
                    if river_d2["id"] == rf["river_id"]:
                        for node_d2 in river_d2.get("nodes", []):
                            nstatus = node_d2.get("status", "active")
                            if (node_d2["layer"] == rf["layer"]
                                    and nstatus in ("active", "weak")
                                    and node_d2["ticker"] != ticker):
                                active_weak_count += 1
                                t_prices = all_prices.get(node_d2["ticker"], {})
                                r4w = t_prices.get("4w")
                                if r4w is not None:
                                    peer_4w_returns.append(r4w)
            d2 = score_d2(peer_4w_returns, active_weak_count, has_minkabu)

            # D3
            d3_candidate_4w = p.get("4w")
            d3_candidate_12w = p.get("12w")
            layer_key = (rf["river_id"], rf["layer"]) if rf else None
            la_full = layer_avgs.get(layer_key, {}) if layer_key else {}
            peer_avg_4w = la_full.get("avg_4w")
            peer_avg_12w = la_full.get("avg_12w")
            valid_peer_count = sum(1 for r4w in peer_4w_returns if r4w is not None)
            d3_val, weak_peer_set = score_d3(
                d3_candidate_4w, d3_candidate_12w, peer_avg_4w, peer_avg_12w, valid_peer_count
            )

            # D4
            d4_val, best_tier = score_d4(evidence_items)

            # D5
            bbs_speed_latest = b.get("speed_latest")
            bbs_speed_prev = b.get("speed_prev")
            d5 = score_d5(
                bbs_rank_history,
                bbs_speed_latest,
                bbs_speed_prev,
                has_minkabu,
                is_jp_ticker=is_jp,
                has_yahoo_jp_bbs=b.get("has_yahoo_jp_bbs"),
                bbs_rank=b.get("rank"),
                bbs_is_today=b.get("is_today", False),
                bbs_speed_history_recent=b.get("speed_history_recent"),
            )

            # D6
            d6 = score_d6(minkabu_scraped_at, d1)

            # Decision memory
            dec_entry = get_decision_entry(ticker) or {}
            pass_count = dec_entry.get("pass_count", 0) if dec_entry.get("decision") == "pass" else 0
            dm_adj = compute_decision_memory_adjustment(pass_count) if is_suppressed(ticker) else 0

            # Noise penalty
            bbs_rank_val = b.get("rank")
            price_falling = p.get("1m") is not None and p.get("1m", 0) < -5
            has_catalyst_tier1_4 = best_tier <= 4 and d4_val > 0
            prior_pump = False
            high_28d = p.get("high_28d")
            last_close = p.get("last_close")
            if (bbs_rank_val is not None and bbs_rank_val <= 20
                    and high_28d is not None and last_close is not None and high_28d > 0):
                drop_pct = (high_28d - last_close) / high_28d * 100
                if drop_pct >= 20.0:
                    prior_pump = True
            noise = compute_noise_penalty(
                bbs_rank=bbs_rank_val,
                price_falling=price_falling,
                has_catalyst_tier1_4=has_catalyst_tier1_4,
                has_minkabu_support=has_minkabu,
                prior_pump_pattern=prior_pump,
                generic_tag_only=not rf and has_minkabu,
                has_company_specific_evidence=bool(tdnet_items),
                syndicated_only=False,
            )

            new_final_score = compute_final_score(d1, d2, d3_val, d4_val, d5, d6, dm_adj, noise)

            # Queue assignment (deterministic priority order)
            has_tier1_4_source = best_tier <= 4 and d4_val > 0
            ticker_suppressed = is_suppressed(ticker)
            queue_gate_blocked = None
            if ticker_suppressed:
                new_queue = "suppressed"
                queue_gate_blocked = None
            elif d1 == 0 and not has_tier1_4_source:
                new_queue = "C"
                queue_gate_blocked = "no river fit and no Tier 1-4 evidence"
            elif new_final_score >= 70 and d1 > 0 and has_tier1_4_source:
                new_queue = "A"
                queue_gate_blocked = None
            elif new_final_score >= 40 or (node_status in {"active", "weak", "watch"} and d4_val > 0):
                new_queue = "B"
                queue_gate_blocked = None
            else:
                new_queue = "C"
                queue_gate_blocked = None

            rows.append(
                {
                    "ticker": ticker,
                    "name": names.get(ticker, ""),
                    "market": "JP" if ticker.endswith(".T") else "US",
                    # BBS
                    "bbs_rank": b.get("rank") if ticker in bbs else None,
                    "bbs_today": is_today,
                    "speed_latest": b.get("speed_latest"),
                    "speed_prev": b.get("speed_prev"),
                    "speed_trend": b.get("trend"),
                    "has_yahoo_jp_bbs": b.get("has_yahoo_jp_bbs"),
                    # Sentiment
                    "bull_pct": bull_pct,
                    "bear_pct": bear_pct,
                    "eval_scraped_at": s.get("scraped_at"),
                    # River fit
                    "river_id": rf["river_id"] if rf else None,
                    "river_name": rf["river_name"] if rf else None,
                    "layer": rf["layer"] if rf else None,
                    # Price / laggard
                    "return_1y": p.get("1y"),
                    "return_6m": p.get("6m"),
                    "return_3m": p.get("3m"),
                    "return_1m": p.get("1m"),
                    "last_close": p.get("last_close"),
                    "price_date": p.get("last_date"),
                    "layer_avg_1y": layer_avg_1y,
                    "laggard_gap_1y": laggard_gap,
                    # Catalyst
                    "has_tdnet_48h": bool(tdnet_items),
                    "has_minkabu": has_minkabu,
                    # New D1-D6 score components
                    "d1_river_fit": d1,
                    "d2_layer_alpha": d2,
                    "d3_relative_laggard": d3_val,
                    "d4_catalyst": d4_val,
                    "d5_attention_change": d5,
                    "d6_coverage_gap": d6,
                    "raw_score": int(d1 + d2 + d3_val + d4_val + d5 + d6),
                    "decision_memory_adjustment": dm_adj,
                    "noise_penalty": noise,
                    "node_status": node_status,
                    "pass_count": pass_count,
                    "suppress_until": dec_entry.get("suppress_until"),
                    "queue_gate_blocked": queue_gate_blocked,
                    "weak_peer_set": weak_peer_set,
                    "evidence_packet": evidence_items,
                    # Score (new model overrides legacy)
                    "score": new_final_score,
                    "queue": new_queue,
                    "queue_reason": reason,
                }
            )

        # Apply suppression penalty — suppressed "pass" tickers get score capped at 5
        # and are moved to suppressed queue so they don't consume attention
        try:
            from elephant.decisions import get as get_decision
            from elephant.decisions import is_suppressed

            for row in rows:
                t = row["ticker"]
                if is_suppressed(t):
                    row["score"] = min(row["score"], 5)
                    row["queue"] = "suppressed"
                    dec = get_decision(t)
                    row["queue_reason"] = f"suppressed until {dec['suppress_until']}: {dec.get('reason', '')}"
                    row["suppressed"] = True
                else:
                    row["suppressed"] = False
        except Exception:
            for row in rows:
                row.setdefault("suppressed", False)

        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows
