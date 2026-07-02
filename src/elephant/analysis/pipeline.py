from datetime import date
from pathlib import Path

import pandas as pd

from elephant.analysis.aggregate import aggregate_signals
from elephant.analysis.analyzers import analyze_data
from elephant.analysis.catalog import DATA_CATALOG, list_data
from elephant.analysis.models import AggregateScore, EvidencePacket
from elephant.config import DATA_DIR
from elephant.framework import HarvesterResult, Store
from elephant.ticker_registry import normalize_ticker


def build_evidence_packet(ticker: str, data_ids: list[str] | None = None, analysis_date: str | None = None) -> EvidencePacket:
    canonical = normalize_ticker(ticker)
    analysis_date = analysis_date or date.today().isoformat()
    ids = data_ids or [d.data_id for d in list_data()]
    signals = []
    for data_id in ids:
        if data_id not in DATA_CATALOG:
            raise ValueError(f"Unknown analysis data: {data_id}")
        signal = analyze_data(canonical, data_id)
        if signal:
            signals.append(signal)
    return EvidencePacket(canonical, analysis_date, signals)


def analyze_ticker(ticker: str, data_ids: list[str] | None = None, analysis_date: str | None = None) -> tuple[EvidencePacket, AggregateScore]:
    packet = build_evidence_packet(ticker, data_ids=data_ids, analysis_date=analysis_date)
    aggregate = aggregate_signals(packet.ticker, packet.signals, analysis_date=packet.date)
    return packet, aggregate


def save_analysis(packet: EvidencePacket, aggregate: AggregateScore, data_dir: str = DATA_DIR) -> None:
    store = Store(data_dir)
    store.save(
        "ticker_analysis_signals",
        HarvesterResult(
            tags={"ticker": packet.ticker, "date": packet.date},
            data=[s.to_dict() for s in packet.signals],
        ),
    )
    store.save(
        "ticker_analysis_scores",
        HarvesterResult(
            tags={"ticker": packet.ticker, "date": packet.date},
            data=[aggregate.to_dict()],
        ),
    )


def load_latest_score(ticker: str, data_dir: str = DATA_DIR) -> dict | None:
    canonical = normalize_ticker(ticker)
    root = Path(data_dir) / "dataset=ticker_analysis_scores" / f"ticker={canonical}"
    files = sorted(root.glob("date=*/data.parquet"), reverse=True)
    if not files:
        return None
    try:
        df = pd.read_parquet(files[0])
    except Exception:
        return None
    if df.empty:
        return None
    return df.iloc[-1].to_dict()

