from dataclasses import asdict, dataclass

from elephant.analysis.models import DataKind


@dataclass(frozen=True)
class AnalysisDataDefinition:
    data_id: str
    dataset: str
    kind: DataKind
    analyzer: str
    ticker_scoped: bool
    freshness_window_days: int
    source_quality: float
    weight: float
    requires_llm: bool = False
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


DATA_CATALOG: dict[str, AnalysisDataDefinition] = {
    "yjp_bbs_sentiment": AnalysisDataDefinition(
        data_id="yjp_bbs_sentiment",
        dataset="yahoo_evaluations",
        kind="numbered",
        analyzer="yjp_bbs_sentiment",
        ticker_scoped=True,
        freshness_window_days=7,
        source_quality=0.55,
        weight=0.8,
        description="Yahoo JP BBS bull/bear evaluation graph.",
    ),
    "yjp_bbs_speed": AnalysisDataDefinition(
        data_id="yjp_bbs_speed",
        dataset="tickers.cache.json",
        kind="numbered",
        analyzer="yjp_bbs_speed",
        ticker_scoped=True,
        freshness_window_days=7,
        source_quality=0.45,
        weight=0.45,
        description="Yahoo JP BBS comment velocity and recent acceleration.",
    ),
    "daily_price_returns": AnalysisDataDefinition(
        data_id="daily_price_returns",
        dataset="daily_prices",
        kind="numbered",
        analyzer="daily_price_returns",
        ticker_scoped=True,
        freshness_window_days=7,
        source_quality=0.8,
        weight=0.7,
        description="1m/3m/1y price return momentum.",
    ),
    "minkabu_user_sentiment": AnalysisDataDefinition(
        data_id="minkabu_user_sentiment",
        dataset="minkabu_raw_html",
        kind="numbered",
        analyzer="minkabu_user_sentiment",
        ticker_scoped=True,
        freshness_window_days=30,
        source_quality=0.55,
        weight=0.7,
        description="Minkabu individual investor buy/sell predictions.",
    ),
    "minkabu_analyst_sentiment": AnalysisDataDefinition(
        data_id="minkabu_analyst_sentiment",
        dataset="minkabu_raw_html",
        kind="numbered",
        analyzer="minkabu_analyst_sentiment",
        ticker_scoped=True,
        freshness_window_days=90,
        source_quality=0.75,
        weight=1.0,
        description="Minkabu analyst consensus, target price, and counts.",
    ),
    "minkabu_research_narrative": AnalysisDataDefinition(
        data_id="minkabu_research_narrative",
        dataset="minkabu_raw_html",
        kind="narrative",
        analyzer="minkabu_research_narrative",
        ticker_scoped=True,
        freshness_window_days=30,
        source_quality=0.65,
        weight=0.8,
        requires_llm=True,
        description="Minkabu stock diagnosis narrative.",
    ),
    "fool_quote_news": AnalysisDataDefinition(
        data_id="fool_quote_news",
        dataset="news_headlines",
        kind="narrative",
        analyzer="fool_quote_news",
        ticker_scoped=True,
        freshness_window_days=14,
        source_quality=0.6,
        weight=0.7,
        requires_llm=True,
        description="Motley Fool ticker news/article metadata.",
    ),
    "tdnet_disclosures": AnalysisDataDefinition(
        data_id="tdnet_disclosures",
        dataset="tdnet_disclosures",
        kind="narrative",
        analyzer="tdnet_disclosures",
        ticker_scoped=False,
        freshness_window_days=14,
        source_quality=0.95,
        weight=1.4,
        requires_llm=True,
        description="TDnet disclosure titles and document links matched by ticker.",
    ),
    "yjp_bbs_comments": AnalysisDataDefinition(
        data_id="yjp_bbs_comments",
        dataset="yahoo_comments",
        kind="narrative",
        analyzer="yjp_bbs_comments",
        ticker_scoped=True,
        freshness_window_days=7,
        source_quality=0.35,
        weight=0.35,
        requires_llm=True,
        description="Recent Yahoo JP BBS comment bodies.",
    ),
}


def list_data(kind: DataKind | None = None) -> list[AnalysisDataDefinition]:
    values = list(DATA_CATALOG.values())
    if kind:
        values = [d for d in values if d.kind == kind]
    return sorted(values, key=lambda d: (d.kind, d.data_id))


def get_data(data_id: str) -> AnalysisDataDefinition:
    try:
        return DATA_CATALOG[data_id]
    except KeyError:
        raise ValueError(f"Unknown analysis data: {data_id}") from None

