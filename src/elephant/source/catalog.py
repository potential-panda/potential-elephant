from dataclasses import asdict, dataclass
from typing import Literal


SourceScope = Literal["market", "ticker"]
Market = Literal["JP", "US"]


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    name: str
    scope: SourceScope
    markets: tuple[Market, ...]
    dataset: str
    harvester: str
    availability_check_required: bool
    cadence: str
    schedule_time: str | None = None
    max_parallel: int = 1
    min_spacing_minutes: int = 5
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


SOURCES: dict[str, SourceDefinition] = {
    "tdnet_disclosures": SourceDefinition(
        source_id="tdnet_disclosures",
        name="TDnet Disclosures",
        scope="market",
        markets=("JP",),
        dataset="tdnet_disclosures",
        harvester="tdnet",
        availability_check_required=False,
        cadence="daily",
        schedule_time="19:00",
        description="Tokyo Stock Exchange timely disclosure listing. Market-wide source.",
    ),
    "daily_prices": SourceDefinition(
        source_id="daily_prices",
        name="Daily Prices",
        scope="ticker",
        markets=("JP", "US"),
        dataset="daily_prices",
        harvester="price",
        availability_check_required=False,
        cadence="daily",
        max_parallel=2,
        min_spacing_minutes=1,
        description="Ticker price bars fetched through yfinance. No source URL availability check.",
    ),
    "yahoo_jp_bbs": SourceDefinition(
        source_id="yahoo_jp_bbs",
        name="Yahoo Finance JP BBS",
        scope="ticker",
        markets=("JP", "US"),
        dataset="yahoo_comments,yahoo_evaluations",
        harvester="yahoo_jp_bbs",
        availability_check_required=True,
        cadence="daily",
        max_parallel=1,
        min_spacing_minutes=5,
        description="Yahoo Finance Japan forum comments and evaluation graph.",
    ),
    "minkabu": SourceDefinition(
        source_id="minkabu",
        name="Minkabu",
        scope="ticker",
        markets=("JP", "US"),
        dataset="minkabu_raw_html",
        harvester="minkabu",
        availability_check_required=True,
        cadence="daily",
        max_parallel=1,
        min_spacing_minutes=5,
        description="Ticker-scoped Minkabu analysis, research, pick, and analyst consensus pages.",
    ),
    "fool_quote_news": SourceDefinition(
        source_id="fool_quote_news",
        name="Motley Fool Quote News",
        scope="ticker",
        markets=("US",),
        dataset="news_headlines",
        harvester="fool_quote_news",
        availability_check_required=True,
        cadence="3x_daily",
        max_parallel=1,
        min_spacing_minutes=3,
        description="Ticker-scoped Fool quote-page article metadata.",
    ),
}


def list_sources(scope: SourceScope | None = None, enabled_only: bool = True) -> list[SourceDefinition]:
    result = list(SOURCES.values())
    if scope:
        result = [s for s in result if s.scope == scope]
    if enabled_only:
        result = [s for s in result if s.enabled]
    return sorted(result, key=lambda s: (s.scope, s.source_id))


def get_source(source_id: str) -> SourceDefinition:
    try:
        return SOURCES[source_id]
    except KeyError:
        raise ValueError(f"Unknown source: {source_id}") from None

