import random
from datetime import datetime
from typing import List

from elephant.framework import HarvesterTask, Planner, Store
from elephant.news.harvester import NewsHarvester

# Fetch news 3 times a day so the digest always has fresh headlines.
SCHEDULED_HOURS = [7, 12, 18]


class NewsPlanner(Planner):
    def __init__(self, store: Store):
        self.store = store

    def create(self) -> List[HarvesterTask]:
        today = datetime.now()
        harvester = NewsHarvester(self.store)
        tasks = []
        for hour in SCHEDULED_HOURS:
            minute = random.randint(0, 15)
            scheduled_at = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
            tasks.append(HarvesterTask(harvester=harvester, scheduled_at=scheduled_at, args={}))
        return tasks
