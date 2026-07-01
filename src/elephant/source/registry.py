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

    def upsert_availability(self, availability: SourceAvailability) -> None:
        ticker = availability.ticker
        record = self.data.setdefault(ticker, {"market": market_for_ticker(ticker), "sources": {}})
        record.setdefault("sources", {})[availability.source_id] = asdict(availability)

    def available_sources(self, source_id: str | None = None) -> list[tuple[str, str, dict]]:
        rows = []
        for ticker, record in sorted(self.data.items()):
            for sid, source in sorted(record.get("sources", {}).items()):
                if source_id and sid != source_id:
                    continue
                if source.get("status") == "available" and source.get("urls"):
                    rows.append((ticker, sid, source))
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

