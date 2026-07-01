import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elephant.source.availability import source_symbol_and_urls
from elephant.source.catalog import get_source, list_sources
from elephant.source.harvest import SourceHarvestTask, tasks_for_ticker
from elephant.source.registry import SourceAvailability, SourceRegistry
from elephant.source.scheduler import create_daily_plan


def test_source_catalog_defines_market_and_ticker_sources():
    market = {s.source_id for s in list_sources(scope="market")}
    ticker = {s.source_id for s in list_sources(scope="ticker")}

    assert market == {"tdnet_disclosures"}
    assert {"daily_prices", "yahoo_jp_bbs", "minkabu", "fool_quote_news"} <= ticker
    assert get_source("tdnet_disclosures").schedule_time == "19:00"


def test_source_symbol_resolution_consumes_source_specific_ticker_gaps():
    assert source_symbol_and_urls("minkabu", "7203.T") == ("7203", ["https://minkabu.jp/stock/7203"])
    assert source_symbol_and_urls("minkabu", "SMCI") == ("SMCI", ["https://us.minkabu.jp/stock/SMCI"])
    assert source_symbol_and_urls("yahoo_jp_bbs", "7203.T") == (
        "7203.T",
        ["https://finance.yahoo.co.jp/quote/7203.T/forum"],
    )
    assert source_symbol_and_urls("fool_quote_news", "SMCI")[1][0] == "https://www.fool.com/quote/nasdaq/smci/"


def test_source_registry_drives_ticker_harvest_tasks(tmp_path):
    registry = SourceRegistry(str(tmp_path / "source_registry.json"))
    registry.upsert_availability(
        SourceAvailability(
            ticker="SMCI",
            source_id="fool_quote_news",
            status="available",
            source_symbol="smci",
            urls=["https://www.fool.com/quote/nasdaq/smci/"],
        )
    )

    tasks = tasks_for_ticker("SMCI", registry)

    assert any(t.source_id == "fool_quote_news" and t.url == "https://www.fool.com/quote/nasdaq/smci/" for t in tasks)
    assert any(t.source_id == "daily_prices" and t.url == "yfinance://SMCI" for t in tasks)


def test_daily_plan_includes_market_sources_and_registry_ticker_sources(tmp_path):
    registry = SourceRegistry(str(tmp_path / "source_registry.json"))
    registry.upsert_availability(
        SourceAvailability(
            ticker="7203.T",
            source_id="minkabu",
            status="available",
            source_symbol="7203",
            urls=["https://minkabu.jp/stock/7203"],
        )
    )

    plan = create_daily_plan(registry=registry, tickers=[])

    assert any(t.source_id == "tdnet_disclosures" and t.scope == "market" and t.scheduled_at.strftime("%H:%M") == "19:00" for t in plan)
    assert any(t.source_id == "minkabu" and t.ticker == "7203.T" and t.url == "https://minkabu.jp/stock/7203" for t in plan)

