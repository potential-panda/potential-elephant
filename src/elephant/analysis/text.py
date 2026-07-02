import os
import re

from elephant.analysis.models import Direction, DIRECTION_SCORE, direction_from_score


def strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


POSITIVE_TERMS = [
    "買い", "強気", "割安", "上方修正", "増益", "最高益", "受注", "成長", "bull", "buy", "undervalued",
]
NEGATIVE_TERMS = [
    "売り", "弱気", "割高", "下方修正", "減益", "赤字", "警告", "bear", "sell", "overvalued",
]


def heuristic_text_direction(text: str) -> tuple[Direction, float, str]:
    if not text:
        return "unknown", 0.0, "no text"
    lower = text.lower()
    positive = sum(lower.count(term.lower()) for term in POSITIVE_TERMS)
    negative = sum(lower.count(term.lower()) for term in NEGATIVE_TERMS)
    raw = positive - negative
    if raw == 0:
        return "flat", 0.35, "balanced or weak narrative signal"
    score = max(-2.0, min(2.0, raw / 3.0))
    confidence = min(0.75, 0.35 + abs(raw) * 0.08)
    direction = direction_from_score(score)
    return direction, confidence, f"heuristic positive_terms={positive} negative_terms={negative}"


def llm_enabled() -> bool:
    return os.environ.get("ELEPHANT_ANALYSIS_LLM", "").lower() in {"1", "true", "yes"}


def direction_score(direction: Direction) -> float:
    return DIRECTION_SCORE.get(direction, 0.0)

