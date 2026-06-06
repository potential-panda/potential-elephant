import random
from datetime import datetime
from typing import List

from elephant.framework import HarvesterTask, Planner, Store
from elephant.tdnet.harvester import TDnetHarvester

# Run 4x on market days to catch morning, midday, post-close, and evening filings
SCHEDULED_HOURS = [8, 12, 15, 18]


class TDnetPlanner(Planner):
    def __init__(self, store: Store):
        self.store = store

    def create(self) -> List[HarvesterTask]:
        today = datetime.now()
        if today.weekday() >= 5:
            return []

        tasks = []
        for hour in SCHEDULED_HOURS:
            minute = random.randint(0, 10)
            scheduled_at = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
            harvester = TDnetHarvester(self.store)
            tasks.append(HarvesterTask(harvester=harvester, scheduled_at=scheduled_at, args={}))
        return tasks
