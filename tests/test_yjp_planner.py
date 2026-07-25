import json
import os
import sys
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elephant.framework import Store
from elephant.ticker_registry import mark_yahoo_jp_bbs
from elephant.yjp.harvester import YahooFinanceHarvester
from elephant.yjp.planner import YahooFinancePlanner


def _write_atlas(path):
    data = {
        "version": 2,
        "value_chains": [
            {
                "id": "ai_infra",
                "name": "AI Infrastructure Supercycle",
                "companies": [
                    {"ticker": "MSFT", "stage": "driver", "name": "Microsoft"},
                    {"ticker": "AAPL", "stage": "driver", "name": "Apple"},
                    {"ticker": "NVDA", "stage": "prime", "name": "NVIDIA"},
                    {"ticker": "7203.T", "stage": "driver", "name": "Toyota"},
                ],
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_confirmed_us_bbs_tickers_get_full_yahoo_scrape(tmp_path):
    tickers_file = tmp_path / "tickers.txt"
    atlas_path = tmp_path / "atlas.json"
    tickers_file.write_text("3350.T\n", encoding="utf-8")
    _write_atlas(atlas_path)

    mark_yahoo_jp_bbs(str(tickers_file), "MSFT", True)
    mark_yahoo_jp_bbs(str(tickers_file), "AAPL", False)

    planner = YahooFinancePlanner(Store(str(tmp_path)), str(tickers_file), atlas_path=str(atlas_path))
    tasks = planner.create()
    args_by_ticker = {task.harvester.ticker: task.args for task in tasks}

    assert args_by_ticker["3350.T"] == {"max_pages": 10, "max_comments": 200}
    assert args_by_ticker["7203.T"] == {"max_pages": 10, "max_comments": 200}
    assert args_by_ticker["MSFT"] == {"max_pages": 10, "max_comments": 200}

    assert args_by_ticker["NVDA"] == {"max_pages": 3, "max_comments": 50}
    assert "AAPL" not in args_by_ticker


def test_yahoo_evaluations_use_year_partition():
    source = inspect.getsource(YahooFinanceHarvester.scrape)

    assert 'tags={"ticker": self.ticker, "YEAR": scraped_at.strftime("%Y")}' in source
    assert 'tags={"ticker": self.ticker, "date": scraped_at.strftime("%Y-%m-%d")}' in source
