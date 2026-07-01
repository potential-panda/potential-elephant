import random
from datetime import datetime

from elephant.source.catalog import get_source, list_sources
from elephant.source.harvest import SourceHarvestTask
from elephant.source.registry import SourceRegistry
from elephant.source.tickers import known_tickers, market_for_ticker


TICKER_START_MIN = 7 * 60 + 17
TICKER_END_MIN = 23 * 60 + 23


def _distributed_times(count: int, start_min: int = TICKER_START_MIN, end_min: int = TICKER_END_MIN) -> list[int]:
    if count <= 0:
        return []
    span = max(1, end_min - start_min)
    if count == 1:
        return [start_min]
    return [start_min + int(i * span / (count - 1)) for i in range(count)]


def create_daily_plan(registry: SourceRegistry | None = None, tickers: list[str] | None = None) -> list[SourceHarvestTask]:
    registry = registry or SourceRegistry()
    today = datetime.now()
    tasks: list[SourceHarvestTask] = []

    for source in list_sources(scope="market"):
        if source.schedule_time:
            hour, minute = [int(x) for x in source.schedule_time.split(":", 1)]
        else:
            hour, minute = 19, 0
        tasks.append(SourceHarvestTask(source.source_id, "market", today.replace(hour=hour, minute=minute, second=0, microsecond=0)))

    ticker_tasks: list[SourceHarvestTask] = []
    for source in list_sources(scope="ticker"):
        if source.availability_check_required:
            for ticker, _sid, record in registry.available_sources(source.source_id):
                ticker_tasks.append(SourceHarvestTask(source.source_id, "ticker", today, ticker, record["urls"][0]))
        elif source.source_id == "daily_prices":
            for ticker in tickers or known_tickers():
                if market_for_ticker(ticker) in source.markets:
                    ticker_tasks.append(SourceHarvestTask(source.source_id, "ticker", today, ticker, f"yfinance://{ticker}"))

    minutes = _distributed_times(len(ticker_tasks))
    random.shuffle(minutes)
    for task, minute_of_day in zip(ticker_tasks, minutes):
        task.scheduled_at = today.replace(hour=minute_of_day // 60, minute=minute_of_day % 60, second=0, microsecond=0)
        tasks.append(task)

    return sorted(tasks, key=lambda t: t.scheduled_at)


def due_availability_sources() -> list[str]:
    return [s.source_id for s in list_sources(scope="ticker") if s.availability_check_required]

