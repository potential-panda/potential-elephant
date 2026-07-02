import math
import re
from datetime import datetime
from typing import Callable

import pandas as pd

from elephant.analysis.catalog import get_data
from elephant.analysis.loaders import (
    load_minkabu,
    load_news_for_ticker,
    load_prices,
    load_speed_history,
    load_tdnet_for_ticker,
    load_yjp_comments,
    load_yjp_evaluations,
)
from elephant.analysis.models import AnalysisSignal, DIRECTION_SCORE, direction_from_score
from elephant.analysis.text import heuristic_text_direction, strip_html
from elephant.ticker_registry import normalize_ticker


def _freshness_days(value) -> float | None:
    try:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return None
        if getattr(dt, "tzinfo", None):
            dt = dt.tz_convert(None)
        return max(0.0, (datetime.now() - dt.to_pydatetime()).total_seconds() / 86400)
    except Exception:
        return None


def _safe_float(value) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def _signal(ticker: str, data_id: str, direction: str, confidence: float, reason: str, *, numeric=None, evidence=None, freshness_days=None) -> AnalysisSignal:
    definition = get_data(data_id)
    return AnalysisSignal(
        ticker=normalize_ticker(ticker),
        data_id=data_id,
        kind=definition.kind,
        direction=direction,
        score=DIRECTION_SCORE.get(direction, 0.0),
        confidence=max(0.0, min(1.0, confidence)),
        reason=reason,
        numeric=numeric or {},
        evidence=evidence or [],
        freshness_days=freshness_days,
        source_quality=definition.source_quality,
        weight=definition.weight,
    )


def analyze_yjp_bbs_sentiment(ticker: str) -> AnalysisSignal | None:
    df = load_yjp_evaluations(ticker)
    if df.empty:
        return None
    df["scraped_at"] = pd.to_datetime(df.get("scraped_at"), errors="coerce")
    row = df.sort_values("scraped_at").iloc[-1]
    strongest = _safe_float(row.get("strongest"))
    strong = _safe_float(row.get("strong"))
    both = _safe_float(row.get("both"))
    weak = _safe_float(row.get("weak"))
    weakest = _safe_float(row.get("weakest"))
    bull = strongest + strong
    bear = weak + weakest
    spread = bull - bear
    if bull >= 75 and spread >= 40:
        direction = "strong_bull"
    elif bull >= 55 and spread >= 10:
        direction = "bull"
    elif bear >= 75 and spread <= -40:
        direction = "strong_bear"
    elif bear >= 55 and spread <= -10:
        direction = "bear"
    else:
        direction = "flat"
    return _signal(
        ticker,
        "yjp_bbs_sentiment",
        direction,
        0.7,
        f"BBS bull={bull:.1f}% bear={bear:.1f}%",
        numeric={"bull_pct": bull, "bear_pct": bear, "neutral_pct": both, "spread": spread},
        freshness_days=_freshness_days(row.get("scraped_at")),
    )


def analyze_yjp_bbs_speed(ticker: str) -> AnalysisSignal | None:
    history = load_speed_history(ticker)
    if not history:
        return None
    latest = history[0]
    speed = float(latest.get("comments_per_hour") or 0)
    prev = float(history[1].get("comments_per_hour") or 0) if len(history) > 1 else 0
    ratio = speed / prev if prev > 0 else None
    if speed >= 50 or (ratio and ratio >= 2):
        direction = "strong_bull"
    elif speed >= 10 or (ratio and ratio >= 1.3):
        direction = "bull"
    elif ratio and ratio <= 0.5:
        direction = "bear"
    else:
        direction = "flat"
    return _signal(
        ticker,
        "yjp_bbs_speed",
        direction,
        0.45,
        f"BBS speed={speed:.2f}/h prev={prev:.2f}/h",
        numeric={"comments_per_hour": speed, "previous_comments_per_hour": prev, "ratio": ratio},
    )


def _pct_change(df: pd.DataFrame, days: int) -> float | None:
    if df.empty:
        return None
    df = df.dropna(subset=["close"]).sort_values("date")
    if df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    latest = df["date"].max()
    start = df[df["date"] <= latest - pd.Timedelta(days=days)]
    if start.empty:
        return None
    start_close = float(start.iloc[-1]["close"])
    end_close = float(df.iloc[-1]["close"])
    if start_close == 0:
        return None
    return round((end_close - start_close) / start_close * 100, 2)


def analyze_daily_price_returns(ticker: str) -> AnalysisSignal | None:
    df = load_prices(ticker)
    if df.empty:
        return None
    r1m = _pct_change(df, 30)
    r3m = _pct_change(df, 90)
    r1y = _pct_change(df, 365)
    basis = next((v for v in [r1m, r3m, r1y] if v is not None), None)
    if basis is None:
        return None
    if r1m is not None and r1m >= 25:
        direction = "strong_bull"
    elif r1m is not None and r1m >= 8:
        direction = "bull"
    elif r1m is not None and r1m <= -25:
        direction = "strong_bear"
    elif r1m is not None and r1m <= -8:
        direction = "bear"
    else:
        direction = "flat"
    latest_date = pd.to_datetime(df.get("date"), errors="coerce").max()
    return _signal(
        ticker,
        "daily_price_returns",
        direction,
        0.65,
        f"price returns 1m={r1m} 3m={r3m} 1y={r1y}",
        numeric={"return_1m": r1m, "return_3m": r3m, "return_1y": r1y},
        freshness_days=_freshness_days(latest_date),
    )


def _latest_minkabu_text(ticker: str, field: str) -> tuple[str, object] | None:
    df = load_minkabu(ticker)
    if df.empty or field not in df.columns:
        return None
    df["scraped_at"] = pd.to_datetime(df.get("scraped_at"), errors="coerce")
    row = df.sort_values("scraped_at").iloc[-1]
    text = strip_html(str(row.get(field) or ""))
    if not text:
        return None
    return text, row.get("scraped_at")


def analyze_minkabu_user_sentiment(ticker: str) -> AnalysisSignal | None:
    loaded = _latest_minkabu_text(ticker, "pick")
    if not loaded:
        return None
    text, scraped_at = loaded
    buy_match = re.search(r"買い予想[:：]\s*([\d,]+)件", text)
    sell_match = re.search(r"売り予想[:：]\s*([\d,]+)件", text)
    buy = int(buy_match.group(1).replace(",", "")) if buy_match else None
    sell = int(sell_match.group(1).replace(",", "")) if sell_match else None
    if buy is None or sell is None or buy + sell == 0:
        direction, confidence, reason = heuristic_text_direction(text)
        numeric = {}
    else:
        bull_pct = buy / (buy + sell) * 100
        if bull_pct >= 80:
            direction = "strong_bull"
        elif bull_pct >= 60:
            direction = "bull"
        elif bull_pct <= 20:
            direction = "strong_bear"
        elif bull_pct <= 40:
            direction = "bear"
        else:
            direction = "flat"
        confidence = min(0.8, 0.4 + math.log10(buy + sell + 1) / 5)
        reason = f"Minkabu users buy={buy} sell={sell}"
        numeric = {"user_buy_count": buy, "user_sell_count": sell, "user_bull_pct": round(bull_pct, 2)}
    return _signal(ticker, "minkabu_user_sentiment", direction, confidence, reason, numeric=numeric, freshness_days=_freshness_days(scraped_at))


def analyze_minkabu_analyst_sentiment(ticker: str) -> AnalysisSignal | None:
    loaded = _latest_minkabu_text(ticker, "analyst_consensus")
    if not loaded:
        return None
    text, scraped_at = loaded
    strong_buy = re.search(r"強気買い\s*([\d,]+)人", text)
    buy = re.search(r"(?<!強気)買い\s*([\d,]+)人", text)
    neutral = re.search(r"中立\s*([\d,]+)人", text)
    sell = re.search(r"売り\s*([\d,]+)人", text)
    counts = {
        "strong_buy": int(strong_buy.group(1).replace(",", "")) if strong_buy else 0,
        "buy": int(buy.group(1).replace(",", "")) if buy else 0,
        "neutral": int(neutral.group(1).replace(",", "")) if neutral else 0,
        "sell": int(sell.group(1).replace(",", "")) if sell else 0,
    }
    target = re.search(r"平均目標株価は\s*([\d,]+)円", text)
    total = sum(counts.values())
    if total:
        score = (counts["strong_buy"] * 2 + counts["buy"] - counts["sell"]) / total
        direction = direction_from_score(score)
        confidence = min(0.9, 0.45 + total / 30)
        reason = f"Minkabu analysts {counts}"
    else:
        direction, confidence, reason = heuristic_text_direction(text)
    numeric = {**counts, "analyst_count": total}
    if target:
        numeric["target_price"] = float(target.group(1).replace(",", ""))
    return _signal(ticker, "minkabu_analyst_sentiment", direction, confidence, reason, numeric=numeric, freshness_days=_freshness_days(scraped_at))


def analyze_minkabu_research_narrative(ticker: str) -> AnalysisSignal | None:
    loaded = _latest_minkabu_text(ticker, "research")
    if not loaded:
        return None
    text, scraped_at = loaded
    direction, confidence, reason = heuristic_text_direction(text)
    return _signal(
        ticker,
        "minkabu_research_narrative",
        direction,
        confidence,
        reason,
        evidence=[{"text": text[:600]}],
        freshness_days=_freshness_days(scraped_at),
    )


def analyze_fool_quote_news(ticker: str) -> AnalysisSignal | None:
    df = load_news_for_ticker(ticker)
    if df.empty:
        return None
    df = df.sort_values("scraped_at" if "scraped_at" in df.columns else df.columns[0], ascending=False)
    text = " ".join(str(v) for v in df.head(10).get("title", []))
    direction, confidence, reason = heuristic_text_direction(text)
    evidence = [
        {"title": row.get("title"), "url": row.get("url"), "source": row.get("source")}
        for _, row in df.head(10).iterrows()
    ]
    return _signal(ticker, "fool_quote_news", direction, confidence, reason, evidence=evidence, numeric={"article_count": len(df)})


def analyze_tdnet_disclosures(ticker: str) -> AnalysisSignal | None:
    df = load_tdnet_for_ticker(ticker)
    if df.empty:
        return None
    text = " ".join(str(v) for v in df.get("title", []))
    direction, confidence, reason = heuristic_text_direction(text)
    evidence = [
        {"title": row.get("title"), "url": row.get("document_url"), "date": row.get("date")}
        for _, row in df.head(20).iterrows()
    ]
    return _signal(ticker, "tdnet_disclosures", direction, min(0.95, max(confidence, 0.55)), reason, evidence=evidence, numeric={"disclosure_count": len(df)})


def analyze_yjp_bbs_comments(ticker: str) -> AnalysisSignal | None:
    df = load_yjp_comments(ticker)
    if df.empty or "body" not in df.columns:
        return None
    df = df.sort_values("scraped_at" if "scraped_at" in df.columns else df.columns[0], ascending=False)
    text = " ".join(str(v) for v in df.head(30)["body"].fillna(""))
    direction, confidence, reason = heuristic_text_direction(text)
    return _signal(ticker, "yjp_bbs_comments", direction, min(confidence, 0.55), reason, evidence=[{"text": text[:800]}], numeric={"comment_count": len(df)})


ANALYZERS: dict[str, Callable[[str], AnalysisSignal | None]] = {
    "yjp_bbs_sentiment": analyze_yjp_bbs_sentiment,
    "yjp_bbs_speed": analyze_yjp_bbs_speed,
    "daily_price_returns": analyze_daily_price_returns,
    "minkabu_user_sentiment": analyze_minkabu_user_sentiment,
    "minkabu_analyst_sentiment": analyze_minkabu_analyst_sentiment,
    "minkabu_research_narrative": analyze_minkabu_research_narrative,
    "fool_quote_news": analyze_fool_quote_news,
    "tdnet_disclosures": analyze_tdnet_disclosures,
    "yjp_bbs_comments": analyze_yjp_bbs_comments,
}


def analyze_data(ticker: str, data_id: str) -> AnalysisSignal | None:
    return ANALYZERS[data_id](ticker)
