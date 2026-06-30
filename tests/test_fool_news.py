import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elephant.news.harvester import _fool_quote_urls, _load_fool_tickers, _parse_fool_card
from elephant.news.harvester import _include_general_news, _load_fool_sources
from elephant.source_registry import SourceAvailability, SourceRegistry


def test_load_fool_tickers_uses_confirmed_us_ticker_file(tmp_path):
    tickers_file = tmp_path / "tickers.txt"
    tickers_file.write_text("")
    (tmp_path / "tickers-us.txt").write_text(
        "SMCI bbs=false minkabu=true\n"
        "MSFT bbs=true minkabu=unknown\n"
        "7203.T bbs=true minkabu=false\n"
    )

    assert _load_fool_tickers({}, str(tickers_file)) == ["SMCI", "MSFT"]


def test_load_fool_tickers_accepts_override_and_skips_jp_tickers(tmp_path):
    tickers_file = tmp_path / "tickers.txt"
    tickers_file.write_text("")

    assert _load_fool_tickers({"fool_tickers": ["smci", "7203.T", "SMCI"]}, str(tickers_file)) == ["SMCI"]


def test_fool_quote_urls_try_common_us_exchanges():
    assert _fool_quote_urls("SMCI") == [
        "https://www.fool.com/quote/nasdaq/smci/",
        "https://www.fool.com/quote/nyse/smci/",
        "https://www.fool.com/quote/amex/smci/",
    ]


def test_parse_fool_card_extracts_article_metadata():
    scraped_at = datetime(2026, 6, 30, 12, 0)
    row = _parse_fool_card(
        {
            "title": "Warning: Supermicro Stock Faces a Critical Trust Test",
            "href": "https://www.fool.com/investing/2026/06/24/warning-supermicro-stock-faces-a-critical-trust-te/",
            "card": "Warning: Supermicro Stock Faces a Critical Trust TestRick OrfordJun 24, 2026",
        },
        "SMCI",
        "https://www.fool.com/quote/nasdaq/smci/",
        scraped_at,
    )

    assert row["source"] == "fool_us_quote_news"
    assert row["ticker"] == "SMCI"
    assert row["title"] == "Warning: Supermicro Stock Faces a Critical Trust Test"
    assert row["author"] == "Rick Orford"
    assert row["published"] == "Jun 24, 2026"
    assert row["quote_url"] == "https://www.fool.com/quote/nasdaq/smci/"
    assert row["scraped_at"] == scraped_at


def test_general_news_is_disabled_by_default():
    assert _include_general_news({}) is False
    assert _include_general_news({"include_general_news": True}) is True


def test_load_fool_sources_uses_source_registry_url(tmp_path):
    registry_path = tmp_path / "source_registry.json"
    registry = SourceRegistry(str(registry_path))
    registry.upsert_availability(
        SourceAvailability(
            ticker="SMCI",
            source_id="fool_quote_news",
            status="available",
            source_symbol="smci",
            urls=["https://www.fool.com/quote/nasdaq/smci/"],
        )
    )
    registry.save()

    assert _load_fool_sources({}, str(registry_path)) == [
        ("SMCI", "https://www.fool.com/quote/nasdaq/smci/")
    ]


def test_load_fool_sources_does_not_guess_without_explicit_override(tmp_path):
    registry_path = tmp_path / "source_registry.json"

    assert _load_fool_sources({}, str(registry_path)) == []
