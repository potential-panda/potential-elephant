import random
from datetime import datetime
from typing import List

from elephant.framework import HarvesterTask, Planner, Store
from elephant.tickers import get_tickers
from elephant.minkabu.harvester import MinkabuHarvester


class MinkabuPlanner(Planner):
    def __init__(self, store: Store, tickers_file: str):
        self.store = store
        self.tickers_file = tickers_file

    def create(self) -> List[HarvesterTask]:
        tickers = get_tickers(self.tickers_file)
        if not tickers:
            return []

        tasks = []
        
        # Consistent time range: 10:17 (617 mins) to 23:23 (1403 mins)
        start_min = 617
        end_min = 1423 
        
        available_minutes = list(range(start_min, end_min + 1))
        random.shuffle(available_minutes)
        
        today = datetime.now()
        
        for i, ticker in enumerate(tickers):
            random_min = available_minutes[i % len(available_minutes)]
            scheduled_at = today.replace(hour=random_min // 60, minute=random_min % 60, second=0, microsecond=0)
            
            harvester = MinkabuHarvester(self.store, ticker)
            
            tasks.append(
                HarvesterTask(
                    harvester=harvester,
                    scheduled_at=scheduled_at,
                    args={} # No additional params for now
                )
            )
        
        random.shuffle(tasks)
        return tasks
