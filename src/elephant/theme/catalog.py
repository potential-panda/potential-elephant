from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class ThemeDefinition:
    theme_id: str
    name: str
    value_chain_id: str
    stage_hint: str
    source: str = "seed"
    source_url: str = ""
    theme_purity: float = 1.0
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


ThemeSourceKind = Literal["theme_index", "theme_page", "etf_holdings"]
ThemeExtractor = Literal["html_theme_links", "html_ticker_regex", "csv_holdings", "html_holdings_regex"]


@dataclass(frozen=True)
class ThemeSourceDefinition:
    source_id: str
    kind: ThemeSourceKind
    theme_id: str
    name: str
    url: str
    extractor: ThemeExtractor
    enabled: bool = True
    issuer: str = ""
    etf: str = ""
    source_quality: float = 0.75
    issuer_quality: float = 1.0
    theme_purity: float = 1.0
    ticker_column: str = "ticker"
    weight_column: str = "holding_weight"
    detail_url_patterns: tuple[str, ...] = ()
    top_n: int = 20
    base_url: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


THEME_DEFINITIONS: dict[str, ThemeDefinition] = {
    "ai_infrastructure": ThemeDefinition(
        "ai_infrastructure",
        "AI Infrastructure",
        "ai_infra",
        "driver",
        source_url="https://minkabu.jp/theme",
        theme_purity=1.0,
        description="AI infrastructure CapEx, data centers, compute buildout.",
    ),
    "ai_semiconductors": ThemeDefinition(
        "ai_semiconductors",
        "AI Semiconductors",
        "ai_infra",
        "prime",
        theme_purity=0.95,
        description="GPU, accelerator, semiconductor, networking, and memory exposure.",
    ),
    "ai_power": ThemeDefinition(
        "ai_power",
        "AI Power and Grid",
        "ai_infra",
        "capacity",
        theme_purity=0.9,
        description="Power generation, nuclear, utilities, and grid capacity for AI load.",
    ),
    "semiconductor_equipment": ThemeDefinition(
        "semiconductor_equipment",
        "Semiconductor Equipment",
        "tech_local",
        "prime",
        theme_purity=0.95,
        description="Lithography, wafer fabrication, inspection, and test equipment.",
    ),
    "factory_automation": ThemeDefinition(
        "factory_automation",
        "Factory Automation",
        "tech_local",
        "capacity",
        theme_purity=0.8,
        description="Automation and industrial equipment for localized manufacturing.",
    ),
    "physical_ai": ThemeDefinition(
        "physical_ai",
        "Physical AI",
        "physical_ai",
        "driver",
        source_url="https://minkabu.jp/theme/%E3%83%95%E3%82%A3%E3%82%B8%E3%82%AB%E3%83%ABAI",
        theme_purity=1.0,
        description="Embodied AI, robotics, sensors, actuators, and automation.",
    ),
    "robotics": ThemeDefinition(
        "robotics",
        "Robotics and Automation",
        "physical_ai",
        "prime",
        theme_purity=0.9,
        description="Robotics platforms and automation systems.",
    ),
    "robotics_components": ThemeDefinition(
        "robotics_components",
        "Robotics Components",
        "physical_ai",
        "bottleneck",
        theme_purity=0.95,
        description="Motors, gears, sensors, and precision components.",
    ),
    "glp1_longevity": ThemeDefinition(
        "glp1_longevity",
        "GLP-1 and Longevity",
        "longevity",
        "driver",
        theme_purity=0.95,
        description="GLP-1, metabolic therapies, and demographic longevity demand.",
    ),
    "medtech_devices": ThemeDefinition(
        "medtech_devices",
        "Medical Technology Devices",
        "longevity",
        "prime",
        theme_purity=0.8,
        description="Medical devices, surgical robotics, diabetes devices, and care platforms.",
    ),
    "pharma_supply_chain": ThemeDefinition(
        "pharma_supply_chain",
        "Pharma Supply Chain",
        "longevity",
        "capacity",
        theme_purity=0.85,
        description="Drug delivery, packaging, cold chain, and pharmaceutical distribution.",
    ),
}


THEME_SOURCES: dict[str, ThemeSourceDefinition] = {
    "globalx_jp_fund_list": ThemeSourceDefinition(
        source_id="globalx_jp_fund_list",
        kind="theme_index",
        theme_id="",
        name="Global X Japan Fund List",
        url="https://globalxetfs.co.jp/funds/list.html",
        extractor="html_theme_links",
        source_quality=0.75,
        theme_purity=0.8,
        detail_url_patterns=("/funds/", "/en/funds/"),
        base_url="https://globalxetfs.co.jp",
        top_n=20,
        description="Thematic ETF list; detail pages are treated as curated baskets.",
    ),
    "minkabu_popular_themes": ThemeSourceDefinition(
        source_id="minkabu_popular_themes",
        kind="theme_index",
        theme_id="",
        name="Minkabu Popular Theme Ranking",
        url="https://minkabu.jp/theme/popular_ranking",
        extractor="html_theme_links",
        source_quality=0.8,
        theme_purity=0.9,
        detail_url_patterns=("/theme/",),
        base_url="https://minkabu.jp",
        top_n=20,
        description="Minkabu popular theme ranking; detail pages list related Japanese stocks.",
    ),
    "kabutan_theme_ranking_3d": ThemeSourceDefinition(
        source_id="kabutan_theme_ranking_3d",
        kind="theme_index",
        theme_id="",
        name="Kabutan Theme Access Ranking 3 Days",
        url="https://kabutan.jp/info/accessranking/3_2",
        extractor="html_theme_links",
        source_quality=0.7,
        theme_purity=0.8,
        detail_url_patterns=("/themes/?theme=",),
        base_url="https://kabutan.jp",
        top_n=20,
        description="Kabutan popular theme ranking; detail pages list related Japanese stocks.",
    ),
    "stocktitan_themes": ThemeSourceDefinition(
        source_id="stocktitan_themes",
        kind="theme_index",
        theme_id="",
        name="StockTitan Theme List",
        url="https://www.stocktitan.net/stocks/themes",
        extractor="html_theme_links",
        source_quality=0.65,
        theme_purity=0.75,
        detail_url_patterns=("/stocks/themes/", "/stocks/theme/"),
        base_url="https://www.stocktitan.net",
        top_n=20,
        description="StockTitan theme directory; detail pages list US stocks by theme.",
    ),
}


ETF_THEME_MAP: dict[str, dict] = {}


THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ai_infrastructure": (
        "ai infrastructure",
        "artificial intelligence",
        "ai&bigdata",
        "ai＆bigデータ",
        "ai＆ビッグデータ",
        "data center",
        "tech top",
        "us tech",
        "us テック",
        "データセンター",
        "生成ai",
        "人工知能",
    ),
    "ai_semiconductors": ("semiconductor", "半導体", "gpu", "hbm", "chip"),
    "ai_power": ("power", "utility", "utilities", "nuclear", "uranium", "ウラニウム", "電力", "原子力"),
    "semiconductor_equipment": ("semiconductor equipment", "半導体製造装置", "lithography", "wafer"),
    "factory_automation": ("factory automation", "automation", "industrial", "fa", "工場自動化"),
    "physical_ai": ("physical ai", "フィジカルai", "embodied ai"),
    "robotics": ("robot", "robotics", "ロボット", "ドローン", "autonomous"),
    "robotics_components": ("motor", "gear", "sensor", "actuator", "モーター", "センサー"),
    "glp1_longevity": ("glp-1", "obesity", "diabetes", "longevity", "肥満", "糖尿病"),
    "medtech_devices": ("medical device", "medtech", "surgical", "healthcare equipment"),
    "pharma_supply_chain": ("pharma supply", "drug delivery", "cold chain", "物流", "医薬品卸"),
}


def list_theme_definitions() -> list[ThemeDefinition]:
    return sorted(THEME_DEFINITIONS.values(), key=lambda theme: theme.theme_id)


def get_theme_definition(theme_id: str) -> ThemeDefinition | None:
    return THEME_DEFINITIONS.get(theme_id)


def list_theme_sources(enabled_only: bool = True) -> list[ThemeSourceDefinition]:
    sources = list(THEME_SOURCES.values())
    if enabled_only:
        sources = [source for source in sources if source.enabled]
    return sorted(sources, key=lambda source: (source.kind, source.source_id))


def get_theme_source(source_id: str) -> ThemeSourceDefinition:
    try:
        return THEME_SOURCES[source_id]
    except KeyError:
        raise ValueError(f"Unknown theme source: {source_id}") from None


def get_etf_theme_source(etf: str) -> ThemeSourceDefinition | None:
    etf = str(etf).strip().upper()
    for source in THEME_SOURCES.values():
        if source.kind == "etf_holdings" and source.etf == etf:
            return source
    return None


def infer_theme_id(name: str, url: str = "") -> str:
    text = f"{name} {url}".lower()
    for theme_id, keywords in THEME_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            return theme_id
    return ""
