import random
from datetime import datetime
from typing import List

from elephant.framework import HarvesterTask, Planner, Store
from elephant.tickers import get_tickers
from elephant.yjp.harvester import YahooFinanceHarvester


class YahooFinancePlanner(Planner):
    def __init__(self, store: Store, tickers_file: str, atlas_path: str = None):
        self.store = store
        self.tickers_file = tickers_file
        self.atlas_path = atlas_path

    def create(self) -> List[HarvesterTask]:
        from elephant.config import SOURCE_REGISTRY_FILE
        from elephant.source_registry import SourceRegistry

        registry_rows = SourceRegistry(SOURCE_REGISTRY_FILE).available_sources("yahoo_jp_bbs")
        if registry_rows:
            tasks = []
            start_min = 617
            end_min = 1423
            available_minutes = list(range(start_min, end_min + 1))
            random.shuffle(available_minutes)
            today = datetime.now()
            for i, (ticker, _source_id, source) in enumerate(registry_rows):
                random_min = available_minutes[i % len(available_minutes)]
                scheduled_at = today.replace(hour=random_min // 60, minute=random_min % 60, second=0, microsecond=0)
                harvester = YahooFinanceHarvester(self.store, ticker, tickers_file=self.tickers_file)
                tasks.append(HarvesterTask(
                    harvester=harvester,
                    scheduled_at=scheduled_at,
                    args={"source_url": source["urls"][0], "max_pages": 10, "max_comments": 200},
                ))
            random.shuffle(tasks)
            return tasks

        from elephant.ticker_registry import is_jp_ticker, load_cache, get_yahoo_jp_bbs_status, load_us_tickers
        all_tickers = get_tickers(self.tickers_file, atlas_path=self.atlas_path)

        # tickers.txt (JP) and tickers-us.txt (confirmed US) together define
        # the daily scraping plan. tickers-us.txt is authoritative when a
        # ticker is listed there (an operator can also hand-edit it). The
        # cache is consulted only as a fallback for confirmed-no tickers
        # that never got registered in tickers-us.txt (neither source ever
        # confirmed a page for them).
        us_status = load_us_tickers(self.tickers_file)
        cache = load_cache(self.tickers_file)

        # JP tickers: always include (sourced from BBS ranking)
        jp_tickers = [t for t in all_tickers if is_jp_ticker(t)]

        # US tickers: atlas names are probed for Yahoo JP BBS availability.
        # Once confirmed in tickers-us.txt, scrape them with the same depth
        # as JP tickers. Confirmed-no (bbs=False) tickers are skipped.
        us_confirmed_tickers = []
        us_probe_tickers = []
        for ticker in all_tickers:
            if is_jp_ticker(ticker):
                continue
            bbs_status = us_status.get(ticker, {}).get("bbs")
            if bbs_status is None:
                bbs_status = get_yahoo_jp_bbs_status(cache, ticker)
            if bbs_status is True:
                us_confirmed_tickers.append(ticker)
            elif bbs_status is None:
                us_probe_tickers.append(ticker)

        full_tickers = jp_tickers + us_confirmed_tickers
        if not full_tickers and not us_probe_tickers:
            return []

        tasks = []

        # Time range: 10:17 (617 mins) to 23:23 (1403 mins)
        start_min = 617
        end_min = 1423
        available_minutes = list(range(start_min, end_min + 1))
        random.shuffle(available_minutes)

        today = datetime.now()

        # JP tickers and confirmed US Yahoo JP BBS tickers: full scrape.
        for i, ticker in enumerate(full_tickers):
            random_min = available_minutes[i % len(available_minutes)]
            scheduled_at = today.replace(hour=random_min // 60, minute=random_min % 60, second=0, microsecond=0)
            harvester = YahooFinanceHarvester(self.store, ticker, tickers_file=self.tickers_file)
            tasks.append(HarvesterTask(
                harvester=harvester,
                scheduled_at=scheduled_at,
                args={"max_pages": 10, "max_comments": 200},
            ))

        # Unprobed US atlas tickers: lighter scrape to discover BBS availability.
        us_start = len(full_tickers)
        for i, ticker in enumerate(us_probe_tickers):
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
