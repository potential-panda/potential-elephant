import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elephant.source_adapters import FoolQuoteNewsAdapter, MinkabuAdapter, YahooJpBbsAdapter
from elephant.source_registry import SourceAvailability, SourceRegistry, market_for_ticker


def test_source_registry_stores_canonical_ticker_and_exact_url(tmp_path):
    path = tmp_path / "source_registry.json"
    registry = SourceRegistry(str(path))
    registry.upsert_availability(
        SourceAvailability(
            ticker="smci",
            source_id="fool_quote_news",
            status="available",
            source_symbol="smci",
            urls=["https://www.fool.com/quote/nasdaq/smci/"],
        )
    )
    registry.save()

    reloaded = SourceRegistry(str(path))
    record = reloaded.get_source("SMCI", "fool_quote_news")

    assert record["ticker"] == "SMCI"
    assert record["status"] == "available"
    assert record["source_symbol"] == "smci"
    assert record["urls"] == ["https://www.fool.com/quote/nasdaq/smci/"]


def test_market_for_ticker_uses_canonical_suffix():
    assert market_for_ticker("7203.T") == "JP"
    assert market_for_ticker("SMCI") == "US"


def test_source_adapters_resolve_source_specific_symbols():
    assert MinkabuAdapter().url_for("7203.T") == ("7203", "https://minkabu.jp/stock/7203")
    assert MinkabuAdapter().url_for("SMCI") == ("SMCI", "https://us.minkabu.jp/stocks/SMCI")
    assert YahooJpBbsAdapter().url_for("7203.T") == ("7203.T", "https://finance.yahoo.co.jp/quote/7203.T/forum")
    assert FoolQuoteNewsAdapter().urls_for("SMCI")[0] == "https://www.fool.com/quote/nasdaq/smci/"
