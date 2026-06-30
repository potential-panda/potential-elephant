from datetime import datetime
from typing import List

from elephant.config import SOURCE_REGISTRY_FILE, TICKERS_FILE, TREE_PATH
from elephant.framework import Harvester, HarvesterResult, HarvesterTask, Planner, Store
from elephant.source_adapters import check_sources
from elephant.source_registry import SourceRegistry
from elephant.tickers import get_tickers


class SourceAvailabilityHarvester(Harvester):
    def __init__(self, store: Store, tickers_file: str = TICKERS_FILE, tree_path: str = TREE_PATH, source_id: str | None = None):
        super().__init__(store)
        self.tickers_file = tickers_file
        self.tree_path = tree_path
        self.source_id = source_id

    def get_url(self, params: dict) -> str:
        return "source-availability://known-tickers"

    async def scrape(self, url: str, params: dict) -> dict[str, HarvesterResult]:
        tickers = params.get("tickers") or get_tickers(self.tickers_file, tree_path=self.tree_path)
        source_id = params.get("source") or self.source_id
        registry = SourceRegistry(SOURCE_REGISTRY_FILE)
        results = await check_sources(tickers, source_id=source_id)
        for availability in results:
            registry.upsert_availability(availability)
        registry.save()
        return {}


class SourceAvailabilityPlanner(Planner):
    def __init__(self, store: Store, tickers_file: str = TICKERS_FILE, tree_path: str = TREE_PATH):
        self.store = store
        self.tickers_file = tickers_file
        self.tree_path = tree_path

    def create(self) -> List[HarvesterTask]:
        today = datetime.now()
        if today.weekday() != 6:  # Sunday
            return []
        harvester = SourceAvailabilityHarvester(self.store, self.tickers_file, self.tree_path)
        scheduled_at = today.replace(hour=3, minute=0, second=0, microsecond=0)
        return [HarvesterTask(harvester=harvester, scheduled_at=scheduled_at, args={})]
