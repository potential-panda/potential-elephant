import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elephant.source.availability import source_symbol_and_urls
import elephant.source.registry as registry_module
from elephant.source.catalog import get_source, list_sources
from elephant.source.harvest import SourceHarvestTask, tasks_for_ticker
from elephant.source.registry import SourceAvailability, SourceRegistry
from elephant.source.scheduler import create_daily_plan
from elephant.source.scheduler_service import SourceSchedulerService


def test_source_catalog_defines_market_and_ticker_sources():
    market = {s.source_id for s in list_sources(scope="market")}
    ticker = {s.source_id for s in list_sources(scope="ticker")}

    assert market == {"tdnet_disclosures", "yjp_bbs_rank"}
    assert {"daily_prices", "yahoo_jp_bbs", "minkabu", "fool_quote_news"} <= ticker
    assert get_source("tdnet_disclosures").schedule_time == "19:00"
    assert get_source("yjp_bbs_rank").schedule_time == "09:47"


def test_source_symbol_resolution_consumes_source_specific_ticker_gaps():
    assert source_symbol_and_urls("minkabu", "7203.T") == ("7203", ["https://minkabu.jp/stock/7203"])
    assert source_symbol_and_urls("minkabu", "SMCI") == ("SMCI", ["https://us.minkabu.jp/stocks/SMCI"])
    assert source_symbol_and_urls("yahoo_jp_bbs", "7203.T") == (
        "7203.T",
        ["https://finance.yahoo.co.jp/quote/7203.T/forum"],
    )
    assert source_symbol_and_urls("fool_quote_news", "SMCI")[1][0] == "https://www.fool.com/quote/nasdaq/smci/"
    assert source_symbol_and_urls("fool_quote_news", "COHR") == (
        "cohr",
        ["https://www.fool.com/quote/nyse/cohr/"],
    )


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


def test_source_registry_infers_availability_from_ticker_dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(registry_module, "DATA_DIR", str(tmp_path))
    data_file = tmp_path / "dataset=yahoo_comments" / "ticker=7203.T" / "date=2026-07-22" / "data.parquet"
    data_file.parent.mkdir(parents=True)
    data_file.write_bytes(b"scraped data exists")
    registry = SourceRegistry(str(tmp_path / "source_registry.json"))

    sources = registry.resolved_sources("7203.T")

    assert sources["yahoo_jp_bbs"]["status"] == "available"
    assert sources["yahoo_jp_bbs"]["urls"] == ["https://finance.yahoo.co.jp/quote/7203.T/forum"]
    assert sources["yahoo_jp_bbs"]["availability_inferred_from_dataset"] is True


def test_ticker_harvest_tasks_use_dataset_backed_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(registry_module, "DATA_DIR", str(tmp_path))
    data_file = tmp_path / "dataset=minkabu_raw_html" / "ticker=7203.T" / "date=2026-07-22" / "data.parquet"
    data_file.parent.mkdir(parents=True)
    data_file.write_bytes(b"scraped data exists")
    registry = SourceRegistry(str(tmp_path / "source_registry.json"))

    tasks = tasks_for_ticker("7203.T", registry)

    assert any(t.source_id == "minkabu" and t.url == "https://minkabu.jp/stock/7203" for t in tasks)
    assert any(t.source_id == "daily_prices" and t.url == "yfinance://7203.T" for t in tasks)


def test_source_registry_assumes_us_minkabu_url():
    registry = SourceRegistry()

    sources = registry.resolved_sources("OKLO")

    assert sources["minkabu"]["status"] == "available"
    assert sources["minkabu"]["urls"] == ["https://us.minkabu.jp/stocks/OKLO"]


def test_source_registry_infers_fool_availability_from_news_dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(registry_module, "DATA_DIR", str(tmp_path))
    data_file = tmp_path / "dataset=news_headlines" / "date=2026-07-21" / "data.parquet"
    data_file.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "source": "fool_us_quote_news",
                "ticker": "ISRG",
                "quote_url": "https://www.fool.com/quote/nasdaq/isrg/",
                "scraped_at": "2026-07-21T16:46:00",
            }
        ]
    ).to_parquet(data_file)
    registry = SourceRegistry(str(tmp_path / "source_registry.json"))

    sources = registry.resolved_sources("ISRG")

    assert sources["fool_quote_news"]["status"] == "available"
    assert sources["fool_quote_news"]["urls"] == ["https://www.fool.com/quote/nasdaq/isrg/"]
    assert sources["fool_quote_news"]["last_row_count"] == 1


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

    assert any(t.source_id == "yjp_bbs_rank" and t.scope == "market" and t.scheduled_at.strftime("%H:%M") == "09:47" for t in plan)
    assert any(t.source_id == "tdnet_disclosures" and t.scope == "market" and t.scheduled_at.strftime("%H:%M") == "19:00" for t in plan)
    assert any(t.source_id == "minkabu" and t.ticker == "7203.T" and t.url == "https://minkabu.jp/stock/7203" for t in plan)


def test_source_scheduler_service_lifecycle():
    service = SourceSchedulerService(max_workers=1)

    assert service.start() is True
    assert service.start() is False
    assert service.status()["running"] is True
    assert service.replan() >= 1
    assert service.stop() is True
