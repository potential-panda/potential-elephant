import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elephant.analysis.aggregate import aggregate_signals
from elephant.analysis.analyzers import analyze_minkabu_analyst_sentiment, analyze_minkabu_user_sentiment
from elephant.analysis.batch import run_daily_analysis
from elephant.analysis.catalog import list_data
from elephant.analysis.models import AnalysisSignal


def test_analysis_catalog_splits_numbered_and_narrative_data():
    numbered = {d.data_id for d in list_data("numbered")}
    narrative = {d.data_id for d in list_data("narrative")}

    assert "yjp_bbs_sentiment" in numbered
    assert "minkabu_analyst_sentiment" in numbered
    assert "fool_quote_news" in narrative
    assert "tdnet_disclosures" in narrative


def test_minkabu_user_sentiment_parser(monkeypatch):
    df = pd.DataFrame([
        {
            "scraped_at": "2026-07-01 12:00:00",
            "pick": "個人予想 売り 売買予想比率 買い 売り 全て：109件 買い予想：97件 売り予想：12件",
        }
    ])
    monkeypatch.setattr("elephant.analysis.analyzers.load_minkabu", lambda ticker: df)

    signal = analyze_minkabu_user_sentiment("5016.T")

    assert signal.direction == "strong_bull"
    assert signal.numeric["user_buy_count"] == 97
    assert signal.numeric["user_sell_count"] == 12


def test_minkabu_analyst_sentiment_parser(monkeypatch):
    df = pd.DataFrame([
        {
            "scraped_at": "2026-07-01 12:00:00",
            "analyst_consensus": "アナリスト判断（コンセンサス）は、買い。内訳は、強気買い5人、買い2人、中立4人となっています。アナリストの平均目標株価は4,930円",
        }
    ])
    monkeypatch.setattr("elephant.analysis.analyzers.load_minkabu", lambda ticker: df)

    signal = analyze_minkabu_analyst_sentiment("5016.T")

    assert signal.direction in {"bull", "strong_bull"}
    assert signal.numeric["strong_buy"] == 5
    assert signal.numeric["buy"] == 2
    assert signal.numeric["neutral"] == 4
    assert signal.numeric["target_price"] == 4930


def test_aggregate_signals_converts_direction_to_0_100_score():
    signals = [
        AnalysisSignal(
            ticker="SMCI",
            data_id="fool_quote_news",
            kind="narrative",
            direction="bull",
            score=1.0,
            confidence=0.8,
            reason="positive",
            source_quality=0.6,
        ),
        AnalysisSignal(
            ticker="SMCI",
            data_id="daily_price_returns",
            kind="numbered",
            direction="bear",
            score=-1.0,
            confidence=0.4,
            reason="weak price",
            source_quality=0.8,
        ),
    ]

    aggregate = aggregate_signals("SMCI", signals, analysis_date="2026-07-01")

    assert aggregate.ticker == "SMCI"
    assert 50 < aggregate.score < 100
    assert aggregate.signal_count == 2
    assert aggregate.supporting_data_ids == ["daily_price_returns", "fool_quote_news"]


def test_daily_analysis_batch_saves_each_ticker(monkeypatch):
    calls = []

    class Packet:
        ticker = "SMCI"
        signals = []

    class Aggregate:
        ticker = "SMCI"

    def fake_analyze(ticker):
        return Packet(), Aggregate()

    def fake_save(packet, aggregate):
        calls.append((packet.ticker, aggregate.ticker))

    monkeypatch.setattr("elephant.analysis.batch.analyze_ticker", fake_analyze)
    monkeypatch.setattr("elephant.analysis.batch.save_analysis", fake_save)

    result = run_daily_analysis(tickers=["SMCI", "SMCI", "NVDA"], limit=1)

    assert result.requested == 1
    assert result.analyzed == 1
    assert result.failed == 0
    assert calls == [("SMCI", "SMCI")]
