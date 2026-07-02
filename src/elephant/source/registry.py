import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from elephant.config import SOURCE_REGISTRY_FILE
from elephant.ticker_registry import normalize_ticker
from elephant.source.tickers import market_for_ticker


STATUSES = {"unknown", "available", "unavailable", "degraded", "retired"}


@dataclass
class SourceAvailability:
    ticker: str
    source_id: str
    status: str
    source_symbol: str = ""
    urls: list[str] | None = None
    checked_at: str = ""
    error: Optional[str] = None

    def __post_init__(self):
        self.ticker = normalize_ticker(str(self.ticker).strip().upper())
        if self.status not in STATUSES:
            raise ValueError(f"Invalid source status: {self.status}")
        if self.urls is None:
            self.urls = []
        if not self.checked_at:
            self.checked_at = datetime.now().isoformat(timespec="seconds")


class SourceRegistry:
    def __init__(self, path: str = SOURCE_REGISTRY_FILE):
        self.path = Path(path)
        self.data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def tickers(self) -> list[str]:
        return sorted(self.data.keys())

    def get_ticker(self, ticker: str) -> dict:
        canonical = normalize_ticker(str(ticker).strip().upper())
        return self.data.get(canonical, {"market": market_for_ticker(canonical), "sources": {}})

    def get_source(self, ticker: str, source_id: str) -> Optional[dict]:
        return self.get_ticker(ticker).get("sources", {}).get(source_id)

    def _assumed_availability(self, ticker: str, source_id: str) -> dict | None:
        from elephant.source.availability import JP_PATTERN_SOURCES, source_symbol_and_urls
        from elephant.source.catalog import get_source

        source = get_source(source_id)
        canonical = normalize_ticker(str(ticker).strip().upper())
        market = market_for_ticker(canonical)
        if source.scope != "ticker" or market not in source.markets:
            return None
        if source.source_id == "daily_prices" or (market == "JP" and source.source_id in JP_PATTERN_SOURCES):
            symbol, urls = source_symbol_and_urls(source_id, canonical)
            return asdict(SourceAvailability(canonical, source_id, "available", symbol, urls))
        return None

    def resolved_sources(self, ticker: str) -> dict[str, dict]:
        canonical = normalize_ticker(str(ticker).strip().upper())
        resolved = dict(self.get_ticker(canonical).get("sources", {}))
        from elephant.source.catalog import list_sources

        for source in list_sources(scope="ticker"):
            if source.source_id in resolved and resolved[source.source_id].get("status") == "available" and resolved[source.source_id].get("urls"):
                continue
            assumed = self._assumed_availability(canonical, source.source_id)
            if assumed:
                resolved[source.source_id] = assumed
        return resolved

    def upsert_availability(self, availability: SourceAvailability) -> None:
        ticker = availability.ticker
        record = self.data.setdefault(ticker, {"market": market_for_ticker(ticker), "sources": {}})
        record.setdefault("sources", {})[availability.source_id] = asdict(availability)

    def available_sources(self, source_id: str | None = None) -> list[tuple[str, str, dict]]:
        rows = []
        from elephant.source.catalog import list_sources
        from elephant.source.tickers import all_known_tickers

        if source_id:
            sources = [s for s in list_sources(scope="ticker") if s.source_id == source_id]
        else:
            sources = list_sources(scope="ticker")

        tickers = []
        seen = set()
        for ticker in list(all_known_tickers()) + self.tickers():
            canonical = normalize_ticker(str(ticker).strip().upper())
            if canonical and canonical not in seen:
                seen.add(canonical)
                tickers.append(canonical)

        for ticker in tickers:
            record = self.get_ticker(ticker)
            raw_sources = record.get("sources", {})
            for source in sources:
                sid = source.source_id
                source_row = raw_sources.get(sid)
                if source_row and source_row.get("status") == "available" and source_row.get("urls"):
                    rows.append((ticker, sid, source_row))
                    continue
                assumed = self._assumed_availability(ticker, sid)
                if assumed:
                    rows.append((ticker, sid, assumed))
        return rows

    def mark_harvested(self, ticker: str, source_id: str, row_count: int = 0, error: str | None = None) -> None:
        source = self.get_source(ticker, source_id)
        if not source:
            return
        source["last_harvested_at"] = datetime.now().isoformat(timespec="seconds")
        source["last_row_count"] = row_count
        source["last_error"] = error
        if error:
            source["consecutive_failures"] = int(source.get("consecutive_failures") or 0) + 1
            if source["consecutive_failures"] >= 3:
                source["status"] = "degraded"
        else:
            source["consecutive_failures"] = 0
