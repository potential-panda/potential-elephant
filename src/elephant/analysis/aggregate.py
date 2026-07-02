from datetime import date

from elephant.analysis.models import AggregateScore, AnalysisSignal, direction_from_score


def aggregate_signals(ticker: str, signals: list[AnalysisSignal], analysis_date: str | None = None) -> AggregateScore:
    analysis_date = analysis_date or date.today().isoformat()
    usable = [s for s in signals if s.direction != "unknown" and s.confidence > 0]
    if not usable:
        return AggregateScore(ticker, analysis_date, 50.0, "unknown", 0.0, 0, [])

    weighted_sum = 0.0
    weight_total = 0.0
    for signal in usable:
        freshness = 1.0
        if signal.freshness_days is not None:
            freshness = max(0.2, min(1.0, 1.0 - signal.freshness_days / 120.0))
        weight = max(0.0, signal.confidence) * max(0.0, signal.source_quality) * max(0.0, signal.weight) * freshness
        weighted_sum += signal.score * weight
        weight_total += weight

    normalized = weighted_sum / weight_total if weight_total else 0.0
    # Convert -2..+2 to 0..100, centered at 50.
    final_score = round(max(0.0, min(100.0, 50.0 + normalized * 25.0)), 2)
    confidence = round(min(1.0, weight_total / max(1.0, len(usable))), 3)
    return AggregateScore(
        ticker=ticker,
        date=analysis_date,
        score=final_score,
        direction=direction_from_score(normalized),
        confidence=confidence,
        signal_count=len(usable),
        supporting_data_ids=sorted({s.data_id for s in usable}),
    )
