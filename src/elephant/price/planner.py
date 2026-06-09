import random
from datetime import datetime
from typing import List

from elephant.framework import HarvesterTask, Planner, Store
from elephant.price.harvester import PriceHarvester
from elephant.tickers import get_tickers


class PricePlanner(Planner):
    def __init__(self, store: Store, tickers_file: str, tree_path: str = None):
        self.store = store
        self.tickers_file = tickers_file
        self.tree_path = tree_path

    def create(self) -> List[HarvesterTask]:
        tickers = get_tickers(self.tickers_file, tree_path=self.tree_path)
        if not tickers:
            return []

        today = datetime.now()
        # Spread fetches between 17:05 and 18:30 (after JP market close at 15:30)
        start_min = 17 * 60 + 5
        end_min = 18 * 60 + 30
        available = list(range(start_min, end_min + 1))
        random.shuffle(available)

        tasks = []
        for i, ticker in enumerate(tickers):
            m = available[i % len(available)]
            scheduled_at = today.replace(hour=m // 60, minute=m % 60, second=0, microsecond=0)
            tasks.append(HarvesterTask(
                harvester=PriceHarvester(self.store, ticker),
                scheduled_at=scheduled_at,
                args={"period": "10d"},
            ))

        random.shuffle(tasks)
        return tasks
