import asyncio
from dataclasses import dataclass
from datetime import datetime

from elephant.config import DATA_DIR, TICKERS_FILE
from elephant.framework import Store
from elephant.minkabu.harvester import MinkabuHarvester
from elephant.news.harvester import NewsHarvester
from elephant.price.harvester import PriceHarvester
from elephant.source.catalog import get_source, list_sources
from elephant.source.registry import SourceRegistry
from elephant.source.run_log import finish_run, start_run
from elephant.tdnet.harvester import TDnetHarvester
from elephant.ticker_registry import normalize_ticker
from elephant.yjp.harvester import YahooFinanceHarvester
from elephant.yjp_bbs_rank.harvester import BbsRankHarvester


@dataclass
class SourceHarvestTask:
    source_id: str
    scope: str
    scheduled_at: datetime
    ticker: str | None = None
    url: str | None = None
    args: dict | None = None


def _row_count(results: dict) -> int:
    total = 0
    for result in results.values():
        total += len(result.data or [])
    return total


async def harvest_task(task: SourceHarvestTask, data_dir: str = DATA_DIR, registry: SourceRegistry | None = None) -> int:
    source = get_source(task.source_id)
    store = Store(data_dir)
    registry = registry or SourceRegistry()
    args = dict(task.args or {})
    run = start_run("harvest", task.source_id, task.scope, ticker=task.ticker, url=task.url)

    try:
        if source.harvester == "tdnet":
            harvester = TDnetHarvester(store)
        elif source.harvester == "yjp_bbs_rank":
            harvester = BbsRankHarvester(store, TICKERS_FILE)
        elif source.harvester == "price":
            if not task.ticker:
                raise ValueError("daily_prices harvest requires ticker")
            harvester = PriceHarvester(store, task.ticker)
        elif source.harvester == "yahoo_jp_bbs":
            if not task.ticker or not task.url:
                raise ValueError("yahoo_jp_bbs harvest requires ticker and url")
            harvester = YahooFinanceHarvester(store, task.ticker)
            args["source_url"] = task.url
        elif source.harvester == "minkabu":
            if not task.ticker or not task.url:
                raise ValueError("minkabu harvest requires ticker and url")
            harvester = MinkabuHarvester(store, task.ticker)
            args["source_url"] = task.url
        elif source.harvester == "fool_quote_news":
            if not task.ticker or not task.url:
                raise ValueError("fool_quote_news harvest requires ticker and url")
            harvester = NewsHarvester(store)
            args["fool_sources"] = [{"ticker": task.ticker, "url": task.url}]
        else:
            raise ValueError(f"Unknown harvester: {source.harvester}")

        url = harvester.get_url(args)
        results = await harvester.scrape(url, args)
        for dataset, result in results.items():
            store.save(dataset, result)
        rows = _row_count(results)
        if task.scope == "ticker" and task.ticker:
            registry.mark_harvested(task.ticker, task.source_id, row_count=rows)
            registry.save()
        finish_run(run, "ok", row_count=rows)
        return rows
    except Exception as exc:
        if task.scope == "ticker" and task.ticker:
            registry.mark_harvested(task.ticker, task.source_id, error=str(exc))
            registry.save()
        finish_run(run, "error", error=str(exc))
        raise


def harvest_task_sync(task: SourceHarvestTask, data_dir: str = DATA_DIR) -> int:
    return asyncio.run(harvest_task(task, data_dir=data_dir))


def tasks_for_ticker(ticker: str, registry: SourceRegistry | None = None) -> list[SourceHarvestTask]:
    registry = registry or SourceRegistry()
    canonical = normalize_ticker(str(ticker).strip().upper())
    tasks = []
    for source in list_sources(scope="ticker"):
        if source.availability_check_required:
            record = registry.get_source(canonical, source.source_id)
            if not record or record.get("status") != "available" or not record.get("urls"):
                continue
            tasks.append(SourceHarvestTask(source.source_id, "ticker", datetime.now(), canonical, record["urls"][0]))
        elif source.source_id == "daily_prices":
            tasks.append(SourceHarvestTask(source.source_id, "ticker", datetime.now(), canonical, f"yfinance://{canonical}"))
    return tasks
