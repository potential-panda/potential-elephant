import random
from datetime import datetime
from typing import List

from elephant.framework import HarvesterTask, Planner, Store
from elephant.tickers import get_tickers
from elephant.yjp.harvester import YahooFinanceHarvester


class YahooFinancePlanner(Planner):
    def __init__(self, store: Store, tickers_file: str, tree_path: str = None):
        self.store = store
        self.tickers_file = tickers_file
        self.tree_path = tree_path

    def create(self) -> List[HarvesterTask]:
        from elephant.ticker_registry import is_jp_ticker, load_cache, get_yahoo_jp_bbs_status
        all_tickers = get_tickers(self.tickers_file, tree_path=self.tree_path)

        cache = load_cache(self.tickers_file)

        # JP tickers: always include (sourced from BBS ranking)
        jp_tickers = [t for t in all_tickers if is_jp_ticker(t)]

        # US tickers: include only if not yet probed OR confirmed to have a BBS page
        us_tickers = [
            t for t in all_tickers
            if not is_jp_ticker(t)
            and get_yahoo_jp_bbs_status(cache, t) is not False
        ]

        if not jp_tickers and not us_tickers:
            return []

        tasks = []

        # Time range: 10:17 (617 mins) to 23:23 (1403 mins)
        start_min = 617
        end_min = 1423
        available_minutes = list(range(start_min, end_min + 1))
        random.shuffle(available_minutes)

        today = datetime.now()

        # JP tickers: full scrape (max 10 pages, 200 comments)
        for i, ticker in enumerate(jp_tickers):
            random_min = available_minutes[i % len(available_minutes)]
            scheduled_at = today.replace(hour=random_min // 60, minute=random_min % 60, second=0, microsecond=0)
            harvester = YahooFinanceHarvester(self.store, ticker, tickers_file=self.tickers_file)
            tasks.append(HarvesterTask(
                harvester=harvester,
                scheduled_at=scheduled_at,
                args={"max_pages": 10, "max_comments": 200},
            ))

        # US tickers: lighter scrape (max 3 pages, 50 comments) — probe + collect
        us_start = len(jp_tickers)
        for i, ticker in enumerate(us_tickers):
            random_min = available_minutes[(us_start + i) % len(available_minutes)]
            scheduled_at = today.replace(hour=random_min // 60, minute=random_min % 60, second=0, microsecond=0)
            harvester = YahooFinanceHarvester(self.store, ticker, tickers_file=self.tickers_file)
            tasks.append(HarvesterTask(
                harvester=harvester,
                scheduled_at=scheduled_at,
                args={"max_pages": 3, "max_comments": 50},
            ))

        random.shuffle(tasks)
        return tasks
