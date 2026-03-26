from datetime import datetime
from typing import List

from elephant.framework import HarvesterTask, Planner, Store
from elephant.yjp_bbs_rank.harvester import BbsRankHarvester

# 30 minutes before the main harvesters start at 10:17
SCHEDULED_HOUR = 9
SCHEDULED_MINUTE = 47


class BbsRankPlanner(Planner):
    def __init__(self, store: Store, tickers_file: str):
        self.store = store
        self.tickers_file = tickers_file

    def create(self) -> List[HarvesterTask]:
        today = datetime.now()
        scheduled_at = today.replace(hour=SCHEDULED_HOUR, minute=SCHEDULED_MINUTE, second=0, microsecond=0)
        harvester = BbsRankHarvester(self.store, self.tickers_file)
        return [HarvesterTask(harvester=harvester, scheduled_at=scheduled_at, args={})]
