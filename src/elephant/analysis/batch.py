import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime

from elephant.analysis.pipeline import analyze_ticker, save_analysis
from elephant.source.tickers import known_tickers
from elephant.ticker_registry import normalize_ticker


@dataclass
class AnalysisBatchResult:
    started_at: str
    finished_at: str
    requested: int
    analyzed: int
    failed: int
    errors: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def run_daily_analysis(tickers: list[str] | None = None, limit: int | None = None) -> AnalysisBatchResult:
    started_at = datetime.now().isoformat(timespec="seconds")
    tickers = tickers or known_tickers()
    deduped = []
    seen = set()
    for ticker in tickers:
        canonical = normalize_ticker(str(ticker).strip().upper())
        if canonical and canonical not in seen:
            seen.add(canonical)
            deduped.append(canonical)
    if limit is not None:
        deduped = deduped[:limit]

    analyzed = 0
    errors = []
    for ticker in deduped:
        try:
            packet, aggregate = analyze_ticker(ticker)
            save_analysis(packet, aggregate)
            analyzed += 1
        except Exception as exc:
            logging.exception("[analysis] failed for %s", ticker)
            errors.append({"ticker": ticker, "error": str(exc)})

    return AnalysisBatchResult(
        started_at=started_at,
        finished_at=datetime.now().isoformat(timespec="seconds"),
        requested=len(deduped),
        analyzed=analyzed,
        failed=len(errors),
        errors=errors[:20],
    )

