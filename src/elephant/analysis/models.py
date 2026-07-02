from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal


DataKind = Literal["numbered", "narrative"]
Direction = Literal["strong_bull", "bull", "flat", "bear", "strong_bear", "unknown"]


DIRECTION_SCORE: dict[Direction, float] = {
    "strong_bull": 2.0,
    "bull": 1.0,
    "flat": 0.0,
    "bear": -1.0,
    "strong_bear": -2.0,
    "unknown": 0.0,
}


def direction_from_score(score: float) -> Direction:
    if score >= 1.5:
        return "strong_bull"
    if score >= 0.5:
        return "bull"
    if score <= -1.5:
        return "strong_bear"
    if score <= -0.5:
        return "bear"
    return "flat"


@dataclass
class AnalysisSignal:
    ticker: str
    data_id: str
    kind: DataKind
    direction: Direction
    score: float
    confidence: float
    reason: str
    evidence: list[dict] = field(default_factory=list)
    numeric: dict = field(default_factory=dict)
    freshness_days: float | None = None
    source_quality: float = 1.0
    weight: float = 1.0
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvidencePacket:
    ticker: str
    date: str
    signals: list[AnalysisSignal]
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "date": self.date,
            "generated_at": self.generated_at,
            "signals": [s.to_dict() for s in self.signals],
        }


@dataclass
class AggregateScore:
    ticker: str
    date: str
    score: float
    direction: Direction
    confidence: float
    signal_count: int
    supporting_data_ids: list[str]
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)
