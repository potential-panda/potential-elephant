import random
from datetime import datetime
from typing import List

from elephant.framework import HarvesterTask, Planner, Store
from elephant.minkabu.harvester import MinkabuHarvester
from elephant.tickers import get_tickers


class MinkabuPlanner(Planner):
    def __init__(self, store: Store, tickers_file: str, tree_path: str = None):
        self.store = store
        self.tickers_file = tickers_file
        self.tree_path = tree_path

    def create(self) -> List[HarvesterTask]:
        from elephant.ticker_registry import is_jp_ticker, load_cache, get_minkabu_us_status
        all_tickers = get_tickers(self.tickers_file, tree_path=self.tree_path)
        cache = load_cache(self.tickers_file)

        # JP tickers: always include (sourced from BBS ranking file)
        jp_tickers = [t for t in all_tickers if is_jp_ticker(t)]

        # US tickers: include only if not yet probed OR confirmed to have a page
        us_tickers = [
            t for t in all_tickers
            if not is_jp_ticker(t)
            and get_minkabu_us_status(cache, t) is not False
        ]

        if not jp_tickers and not us_tickers:
            return []

        tasks = []

        start_min = 617
        end_min = 1423
        available_minutes = list(range(start_min, end_min + 1))
        random.shuffle(available_minutes)

        today = datetime.now()

        for i, ticker in enumerate(jp_tickers):
            random_min = available_minutes[i % len(available_minutes)]
            scheduled_at = today.replace(hour=random_min // 60, minute=random_min % 60, second=0, microsecond=0)
            harvester = MinkabuHarvester(self.store, ticker, tickers_file=self.tickers_file)
            tasks.append(HarvesterTask(harvester=harvester, scheduled_at=scheduled_at, args={}))

        us_start = len(jp_tickers)
        for i, ticker in enumerate(us_tickers):
            random_min = available_minutes[(us_start + i) % len(available_minutes)]
            scheduled_at = today.replace(hour=random_min // 60, minute=random_min % 60, second=0, microsecond=0)
            harvester = MinkabuHarvester(self.store, ticker, tickers_file=self.tickers_file)
            tasks.append(HarvesterTask(harvester=harvester, scheduled_at=scheduled_at, args={}))

        random.shuffle(tasks)
        return tasks
