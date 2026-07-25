import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elephant.theme.builder import build_theme_value_chain_system, build_ticker_theme_scores
from elephant.theme.apply import apply_value_chain_suggestions
from elephant.theme.catalog import get_theme_source, list_theme_sources
from elephant.theme.harvest import harvest_theme_source
from elephant.theme.io import import_etf_holdings_csv, import_theme_members_csv, load_value_chain_suggestions, load_theme_source_themes
from elephant.theme.io import write_dataset
from elephant.atlas.atlas import Atlas


def test_theme_builder_scores_etf_co_membership(tmp_path):
    csv_path = tmp_path / "etf.csv"
    pd.DataFrame(
        [
            {"etf": "BOTZ", "theme_id": "robotics", "ticker": "ISRG", "holding_weight": 8.0, "as_of": "2026-07-01"},
            {"etf": "BOTZ", "theme_id": "robotics", "ticker": "ROK", "holding_weight": 3.0, "as_of": "2026-07-01"},
            {"etf": "ROBO", "theme_id": "robotics", "ticker": "ISRG", "holding_weight": 4.0, "as_of": "2026-07-01"},
        ]
    ).to_csv(csv_path, index=False)

    assert import_etf_holdings_csv(str(csv_path), str(tmp_path)) == 3

    scores = build_ticker_theme_scores(str(tmp_path))
    isrg = scores[(scores["ticker"] == "ISRG") & (scores["theme_id"] == "robotics")].iloc[0]
    rok = scores[(scores["ticker"] == "ROK") & (scores["theme_id"] == "robotics")].iloc[0]

    assert isrg["score"] > rok["score"]
    assert isrg["evidence_count"] == 2


def test_theme_builder_imports_theme_members_and_writes_suggestions(tmp_path):
    csv_path = tmp_path / "members.csv"
    pd.DataFrame(
        [
            {
                "theme_id": "physical_ai",
                "ticker": "6861",
                "name": "Keyence",
                "source": "minkabu_theme",
                "raw_rank": 1,
                "source_weight": 2.0,
            }
        ]
    ).to_csv(csv_path, index=False)

    assert import_theme_members_csv(str(csv_path), str(tmp_path)) == 1
    result = build_theme_value_chain_system(str(tmp_path), atlas_path=str(tmp_path / "atlas.json"), save=True)

    assert result.score_rows == 1
    assert result.suggestion_rows == 1
    suggestions = load_value_chain_suggestions(str(tmp_path))
    row = suggestions.iloc[0]
    assert row["ticker"] == "6861.T"
    assert row["value_chain_id"] == "physical_ai"
    assert row["status"] == "proposed"


def test_theme_sources_are_only_starting_sources():
    sources = list_theme_sources()

    assert {source.source_id for source in sources} == {
        "globalx_jp_fund_list",
        "minkabu_popular_themes",
        "kabutan_theme_ranking_3d",
        "stocktitan_themes",
    }
    assert all(source.kind == "theme_index" for source in sources)


def test_theme_index_harvests_globalx_funds_then_fund_tickers(tmp_path, monkeypatch):
    import elephant.theme.harvest as harvest_module

    index_url = "https://globalxetfs.co.jp/funds/list.html"
    detail_url = "https://globalxetfs.co.jp/funds/2640/index.html"
    csv_url = "https://www.solactive.com/downloads/etfservices/tse-pcf/single/2640.csv"
    pages = {
        index_url: "<a href='/funds/2640/index.html'>グローバルＸ ゲーム＆アニメ-日本株式 ETF</a>",
        detail_url: f"<html><body><a href='{csv_url}'>全銘柄情報</a></body></html>",
        csv_url: (
            "ETF Code,ETF Name,Fund Cash Component,Shares Outstanding,Fund Date\n"
            "2640,Global X Game ETF,0,100,20260727\n\n"
            "Code,Name,ISIN,Exchange,Currency,Shares Amount,Stock Price\n"
            "7974,NINTENDO CO LTD,JP3756600007,XTKS,JPY,100,100\n"
            "7832,BANDAI NAMCO HOLDINGS,JP3778630008,XTKS,JPY,100,100\n"
        ),
    }
    monkeypatch.setattr(harvest_module, "_fetch_text_browser", lambda url, wait_ms=2500: pages[url])
    monkeypatch.setattr(harvest_module, "_fetch_text_with_browser_fallback", lambda url: pages[url])

    dataset, rows = harvest_theme_source(get_theme_source("globalx_jp_fund_list"), str(tmp_path))

    assert dataset == "theme_source_themes,theme_members"
    assert rows == 3
    result = build_theme_value_chain_system(str(tmp_path), atlas_path=str(tmp_path / "atlas.json"), save=True)
    assert result.score_rows == 0
    assert result.suggestion_rows == 0


def test_theme_index_harvests_globalx_us_holdings_from_solactive_csv(tmp_path, monkeypatch):
    import elephant.theme.harvest as harvest_module

    index_url = "https://globalxetfs.co.jp/funds/list.html"
    detail_url = "https://globalxetfs.co.jp/funds/2244/index.html"
    csv_url = "https://www.solactive.com/downloads/etfservices/tse-pcf/single/2244.csv"
    pages = {
        index_url: "<a href='/funds/2244/index.html'>グローバルＸ US テック・トップ20 ETF</a>",
        detail_url: f"<html><body><a href='{csv_url}'>全銘柄情報</a></body></html>",
        csv_url: (
            "ETF Code,ETF Name,Fund Cash Component,Shares Outstanding,Fund Date\n"
            "2244,Global X US Tech Top 20 ETF,0,100,20260727\n\n"
            "Code,Name,ISIN,Exchange,Currency,Shares Amount,Stock Price\n"
            ",APPLE INC,US0378331005,XNAS,USD,100,100\n"
            ",INTUITIVE SURGICAL INC,US46120E6023,XNAS,USD,100,100\n"
            "nan,CASHUSDJPY01,,USD,1,1\n"
        ),
    }
    monkeypatch.setattr(harvest_module, "_fetch_text_browser", lambda url, wait_ms=2500: pages[url])
    monkeypatch.setattr(harvest_module, "_fetch_text_with_browser_fallback", lambda url: pages[url])
    monkeypatch.setattr(
        harvest_module,
        "_resolve_us_symbol",
        lambda isin, name: {"US0378331005": "AAPL", "US46120E6023": "ISRG"}.get(isin, ""),
    )

    dataset, rows = harvest_theme_source(get_theme_source("globalx_jp_fund_list"), str(tmp_path))

    assert dataset == "theme_source_themes,theme_members"
    assert rows == 3
    scores = build_ticker_theme_scores(str(tmp_path))
    assert set(scores["ticker"]) == {"AAPL", "ISRG"}
    assert set(scores["theme_id"]) == {"ai_infrastructure"}
    assert scores["assigned"].all()


def test_apply_uses_market_specific_thresholds(tmp_path):
    atlas_path = tmp_path / "atlas.json"
    atlas = Atlas(str(atlas_path))
    atlas.add_value_chain("ai_infra", "AI Infrastructure")
    write_dataset(
        "value_chain_suggestions",
        [
            {
                "id": "us-low",
                "ticker": "AAPL",
                "market": "US",
                "value_chain_id": "ai_infra",
                "stage": "prime",
                "theme_id": "ai_infrastructure",
                "theme_name": "AI Infrastructure",
                "score": 16.0,
                "confidence": "medium",
                "status": "proposed",
                "evidence_count": 1,
            },
            {
                "id": "jp-low",
                "ticker": "2158.T",
                "market": "JP",
                "value_chain_id": "ai_infra",
                "stage": "driver",
                "theme_id": "ai_infrastructure",
                "theme_name": "AI Infrastructure",
                "score": 16.0,
                "confidence": "medium",
                "status": "proposed",
                "evidence_count": 1,
            },
        ],
        str(tmp_path),
        replace=True,
    )

    result = apply_value_chain_suggestions(
        data_dir=str(tmp_path),
        atlas_path=str(atlas_path),
        min_score=25,
        min_us_score=15,
        remove_low_score=False,
        dry_run=True,
    )

    assert result.evaluated == 1
    assert result.changes[0]["ticker"] == "AAPL"


def test_apply_uses_market_specific_remove_thresholds(tmp_path):
    atlas_path = tmp_path / "atlas.json"
    atlas = Atlas(str(atlas_path))
    atlas.add_value_chain("ai_infra", "AI Infrastructure")
    atlas.add_company("ai_infra", "AAPL", "driver", source="theme_discovery")
    write_dataset(
        "ticker_theme_scores",
        [
            {
                "id": "score-aapl",
                "ticker": "AAPL",
                "theme_id": "ai_infrastructure",
                "value_chain_id": "ai_infra",
                "score": 16.0,
                "evidence_count": 1,
            }
        ],
        str(tmp_path),
        replace=True,
    )

    kept = apply_value_chain_suggestions(
        data_dir=str(tmp_path),
        atlas_path=str(atlas_path),
        remove_min_score=20,
        remove_min_us_score=12,
        dry_run=True,
    )
    removed = apply_value_chain_suggestions(
        data_dir=str(tmp_path),
        atlas_path=str(atlas_path),
        remove_min_score=20,
        dry_run=True,
    )

    assert not any(change["action"] == "remove_company" for change in kept.changes)
    assert any(change["action"] == "remove_company" for change in removed.changes)


def test_theme_index_harvests_themes_then_theme_tickers(tmp_path, monkeypatch):
    import elephant.theme.harvest as harvest_module

    index_url = "https://kabutan.jp/info/accessranking/3_2"
    detail_url = "https://kabutan.jp/themes/?theme=%E3%83%95%E3%82%A3%E3%82%B8%E3%82%AB%E3%83%ABAI"
    pages = {
        index_url: f"<a href='/themes/?theme=%E3%83%95%E3%82%A3%E3%82%B8%E3%82%AB%E3%83%ABAI'>フィジカルAI</a>",
        detail_url: "<html><body><a href='/stock/?code=6861'>6861</a><a href='/stock/?code=6324'>6324</a><a href='/stock/?code=6506'>6506</a></body></html>",
    }
    monkeypatch.setattr(harvest_module, "_fetch_text", lambda url: pages[url])

    dataset, rows = harvest_theme_source(get_theme_source("kabutan_theme_ranking_3d"), str(tmp_path))

    assert dataset == "theme_source_themes,theme_members"
    assert rows == 4
    themes = load_theme_source_themes(str(tmp_path))
    assert themes.iloc[0]["canonical_theme_id"] == "physical_ai"
    result = build_theme_value_chain_system(str(tmp_path), atlas_path=str(tmp_path / "atlas.json"), save=True)
    assert result.score_rows == 3


def test_theme_builder_assigns_top_theme_candidates_relative_to_theme_distribution(tmp_path):
    csv_path = tmp_path / "members.csv"
    pd.DataFrame(
        [
            {"theme_id": "physical_ai", "ticker": "6861", "source": "minkabu_theme", "raw_rank": 1},
            {"theme_id": "physical_ai", "ticker": "6324", "source": "minkabu_theme", "raw_rank": 25},
            {"theme_id": "physical_ai", "ticker": "6506", "source": "minkabu_theme", "raw_rank": 80},
        ]
    ).to_csv(csv_path, index=False)

    assert import_theme_members_csv(str(csv_path), str(tmp_path)) == 3
    scores = build_ticker_theme_scores(str(tmp_path))

    keyence = scores[scores["ticker"] == "6861.T"].iloc[0]
    yaskawa = scores[scores["ticker"] == "6506.T"].iloc[0]
    assert bool(keyence["assigned"]) is True
    assert bool(yaskawa["assigned"]) is False


def test_apply_value_chain_suggestions_requires_explicit_non_dry_run(tmp_path):
    atlas_path = tmp_path / "atlas.json"
    atlas = Atlas(str(atlas_path))
    atlas.add_value_chain("physical_ai", "Physical AI")
    csv_path = tmp_path / "members.csv"
    pd.DataFrame(
        [
            {
                "theme_id": "physical_ai",
                "ticker": "6861",
                "source": "minkabu_theme",
                "raw_rank": 1,
                "source_weight": 2.0,
            }
        ]
    ).to_csv(csv_path, index=False)
    import_theme_members_csv(str(csv_path), str(tmp_path))
    build_theme_value_chain_system(str(tmp_path), atlas_path=str(atlas_path), save=True)

    dry = apply_value_chain_suggestions(data_dir=str(tmp_path), atlas_path=str(atlas_path), min_score=50, dry_run=True)
    assert dry.evaluated == 1
    assert dry.applied == 0
    assert Atlas(str(atlas_path)).find_ticker("6861.T") == []

    applied = apply_value_chain_suggestions(data_dir=str(tmp_path), atlas_path=str(atlas_path), min_score=50, dry_run=False)
    companies = Atlas(str(atlas_path)).find_ticker("6861.T")

    assert applied.applied == 1
    assert len(companies) == 1
    assert companies[0][1].status == "proposed"
    assert companies[0][1].source == "theme_discovery"


def test_apply_value_chain_suggestions_removes_low_score_theme_discovered_companies(tmp_path):
    atlas_path = tmp_path / "atlas.json"
    atlas = Atlas(str(atlas_path))
    atlas.add_value_chain("physical_ai", "Physical AI")
    atlas.add_company("physical_ai", "6861.T", "prime", source="theme_discovery")
    atlas.add_company("physical_ai", "6506.T", "prime", source="manual")

    write_dataset(
        "ticker_theme_scores",
        [
            {
                "id": "score-6861",
                "ticker": "6861.T",
                "theme_id": "physical_ai",
                "value_chain_id": "physical_ai",
                "score": 12.0,
                "evidence_count": 1,
            },
            {
                "id": "score-6506",
                "ticker": "6506.T",
                "theme_id": "physical_ai",
                "value_chain_id": "physical_ai",
                "score": 10.0,
                "evidence_count": 1,
            },
        ],
        str(tmp_path),
        replace=True,
    )

    dry = apply_value_chain_suggestions(data_dir=str(tmp_path), atlas_path=str(atlas_path), dry_run=True)
    assert dry.removed == 0
    assert any(change["action"] == "remove_company" and change["ticker"] == "6861.T" for change in dry.changes)
    assert Atlas(str(atlas_path)).find_ticker("6861.T")

    applied = apply_value_chain_suggestions(data_dir=str(tmp_path), atlas_path=str(atlas_path), dry_run=False)
    updated = Atlas(str(atlas_path))

    assert applied.removed == 1
    assert updated.find_ticker("6861.T") == []
    assert updated.find_ticker("6506.T")


def test_apply_value_chain_suggestions_keeps_human_reviewed_theme_companies(tmp_path):
    atlas_path = tmp_path / "atlas.json"
    atlas = Atlas(str(atlas_path))
    atlas.add_value_chain("physical_ai", "Physical AI")
    atlas.add_company("physical_ai", "6861.T", "prime", source="theme_discovery")
    atlas.update_company(
        "physical_ai",
        "6861.T",
        last_human_decision="keep",
        last_human_decision_date="2026-07-25",
    )

    write_dataset(
        "ticker_theme_scores",
        [
            {
                "id": "score-6861",
                "ticker": "6861.T",
                "theme_id": "physical_ai",
                "value_chain_id": "physical_ai",
                "score": 0.0,
                "evidence_count": 0,
            }
        ],
        str(tmp_path),
        replace=True,
    )

    result = apply_value_chain_suggestions(data_dir=str(tmp_path), atlas_path=str(atlas_path), dry_run=False)

    assert result.removed == 0
    assert Atlas(str(atlas_path)).find_ticker("6861.T")
