import argparse
import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import elephant.secrets as _secrets

_secrets.load()

from elephant.config import SOURCE_REGISTRY_FILE
from elephant.source.availability import check_sources, check_ticker_source
from elephant.source.catalog import get_source, list_sources
from elephant.source.harvest import harvest_task, tasks_for_ticker
from elephant.source.registry import SourceRegistry
from elephant.source.run_log import recent_runs
from elephant.source.scheduler import create_daily_plan
from elephant.source.tickers import known_tickers
from elephant.ticker_registry import normalize_ticker
from elephant.analysis.catalog import list_data
from elephant.analysis.pipeline import analyze_ticker, save_analysis


def sources_list_cmd(args):
    sources = list_sources(scope=args.scope, enabled_only=not args.all)
    for source in sources:
        print(
            f"{source.source_id:<18} {source.scope:<6} {','.join(source.markets):<5} "
            f"{source.dataset:<32} check={source.availability_check_required}"
        )


def sources_check_cmd(args):
    registry = SourceRegistry(SOURCE_REGISTRY_FILE)
    if args.ticker:
        tickers = [normalize_ticker(args.ticker)]
    elif args.all:
        tickers = known_tickers()
    else:
        print("Use --ticker or --all.")
        return

    async def run():
        if args.ticker and args.source:
            return [await check_ticker_source(tickers[0], args.source, registry)]
        return await check_sources(tickers, source_id=args.source, registry=registry)

    results = asyncio.run(run())
    for availability in results:
        urls = ", ".join(availability.urls) if availability.urls else "-"
        print(f"{availability.ticker:<10} {availability.source_id:<18} {availability.status:<11} {urls}")
    print(f"Updated {SOURCE_REGISTRY_FILE}")
    print(f"Checked {len(results)} ticker-source pairs")


def sources_show_cmd(args):
    registry = SourceRegistry(SOURCE_REGISTRY_FILE)
    if args.ticker:
        ticker = normalize_ticker(args.ticker)
        record = registry.get_ticker(ticker)
        print(f"{ticker} ({record.get('market', '')})")
        for source_id, source in sorted(record.get("sources", {}).items()):
            urls = ", ".join(source.get("urls") or []) or "-"
            print(f"  {source_id:<18} {source.get('status','unknown'):<11} {urls}")
        return

    for ticker in registry.tickers():
        record = registry.get_ticker(ticker)
        available = [
            sid for sid, source in record.get("sources", {}).items()
            if source.get("status") == "available"
        ]
        print(f"{ticker:<10} {record.get('market',''):<3} {', '.join(sorted(available)) or '-'}")


def sources_plan_cmd(args):
    registry = SourceRegistry(SOURCE_REGISTRY_FILE)
    tasks = create_daily_plan(registry=registry)
    if args.source:
        tasks = [t for t in tasks if t.source_id == args.source]
    if args.ticker:
        ticker = normalize_ticker(args.ticker)
        tasks = [t for t in tasks if t.ticker == ticker]
    for task in tasks:
        label = task.ticker or "market"
        url = task.url or "-"
        print(f"{task.scheduled_at.strftime('%H:%M')} {task.source_id:<18} {task.scope:<6} {label:<10} {url}")
    print(f"Total tasks: {len(tasks)}")


def _format_task(task):
    label = task.ticker or "market"
    url = task.url or "-"
    return f"{task.scheduled_at.strftime('%H:%M')} {task.source_id:<18} {task.scope:<6} {label:<10} {url}"


def sources_schedule_cmd(args):
    import schedule

    registry = SourceRegistry(SOURCE_REGISTRY_FILE)
    tasks = create_daily_plan(registry=registry)

    if args.dry_run:
        for task in tasks:
            print(_format_task(task))
        print(f"Total tasks: {len(tasks)}")
        return

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    def run_task(task):
        logging.info("Running source task: %s %s %s", task.source_id, task.scope, task.ticker or "market")
        try:
            asyncio.run(harvest_task(task))
        except Exception:
            logging.exception("Source task failed: %s %s", task.source_id, task.ticker or "market")
        return schedule.CancelJob

    def plan_day():
        schedule.clear("source-v2")
        planned = create_daily_plan(registry=SourceRegistry(SOURCE_REGISTRY_FILE))
        for task in planned:
            schedule.every().day.at(task.scheduled_at.strftime("%H:%M")).do(run_task, task=task).tag("source-v2")
        logging.info("Scheduled %d source tasks", len(planned))

    plan_day()
    schedule.every().day.at("01:00").do(plan_day).tag("source-v2")
    while True:
        schedule.run_pending()
        time.sleep(1)


def sources_harvest_cmd(args):
    if args.ticker:
        tasks = tasks_for_ticker(args.ticker)
        if args.source:
            get_source(args.source)
            tasks = [t for t in tasks if t.source_id == args.source]
    elif args.source:
        source = get_source(args.source)
        if source.scope == "market":
            from datetime import datetime
            from elephant.source.harvest import SourceHarvestTask

            tasks = [SourceHarvestTask(source.source_id, source.scope, datetime.now())]
        else:
            print("Ticker-scoped harvest requires --ticker.")
            return
    else:
        print("Use --ticker or --source.")
        return

    async def run():
        rows = 0
        for task in tasks:
            rows += await harvest_task(task)
            print(f"harvested {task.source_id} {task.ticker or 'market'} rows={rows}")
        return rows

    total = asyncio.run(run())
    print(f"Completed {len(tasks)} harvest tasks, rows={total}")


def sources_runs_cmd(args):
    for run in recent_runs(limit=args.limit):
        print(
            f"{run.get('finished_at',''):<19} {run.get('kind',''):<18} {run.get('source_id',''):<18} "
            f"{run.get('ticker') or 'market':<10} {run.get('status',''):<6} rows={run.get('row_count',0)}"
        )


def analysis_catalog_cmd(args):
    for item in list_data(kind=args.kind):
        print(
            f"{item.data_id:<28} {item.kind:<9} {item.dataset:<28} "
            f"weight={item.weight:<4} llm={item.requires_llm}"
        )


def analysis_run_cmd(args):
    packet, aggregate = analyze_ticker(args.ticker)
    if args.save:
        save_analysis(packet, aggregate)
    print(f"{aggregate.ticker} score={aggregate.score} direction={aggregate.direction} confidence={aggregate.confidence}")
    for signal in packet.signals:
        print(
            f"  {signal.data_id:<28} {signal.direction:<12} "
            f"score={signal.score:<4} conf={signal.confidence:<4} {signal.reason}"
        )


def main():
    parser = argparse.ArgumentParser(description="Potential Elephant v2 CLI")
    subparsers = parser.add_subparsers(dest="command")

    sources = subparsers.add_parser("sources", help="Source component commands")
    source_subs = sources.add_subparsers(dest="sources_cmd")

    analysis = subparsers.add_parser("analysis", help="Analysis component commands")
    analysis_subs = analysis.add_subparsers(dest="analysis_cmd")

    list_parser = source_subs.add_parser("list", help="List source catalog")
    list_parser.add_argument("--scope", choices=["market", "ticker"])
    list_parser.add_argument("--all", action="store_true", help="Include disabled sources")

    check_parser = source_subs.add_parser("check", help="Check ticker-source availability")
    check_parser.add_argument("--ticker")
    check_parser.add_argument("--all", action="store_true")
    check_parser.add_argument("--source")

    show_parser = source_subs.add_parser("show", help="Show source registry")
    show_parser.add_argument("--ticker")

    plan_parser = source_subs.add_parser("plan", help="Show source harvest plan")
    plan_parser.add_argument("--ticker")
    plan_parser.add_argument("--source")

    schedule_parser = source_subs.add_parser("schedule", help="Run or inspect the source scheduler")
    schedule_parser.add_argument("--dry-run", action="store_true")

    harvest_parser = source_subs.add_parser("harvest", help="Run source harvest now")
    harvest_parser.add_argument("--ticker")
    harvest_parser.add_argument("--source")

    runs_parser = source_subs.add_parser("runs", help="Show recent source runs")
    runs_parser.add_argument("--limit", type=int, default=50)

    analysis_catalog = analysis_subs.add_parser("catalog", help="List analysis data catalog")
    analysis_catalog.add_argument("--kind", choices=["numbered", "narrative"])

    analysis_run = analysis_subs.add_parser("run", help="Analyze one ticker")
    analysis_run.add_argument("--ticker", required=True)
    analysis_run.add_argument("--save", action="store_true", help="Save analysis signal/score datasets")

    args = parser.parse_args()
    if args.command == "sources":
        if args.sources_cmd == "list":
            sources_list_cmd(args)
        elif args.sources_cmd == "check":
            sources_check_cmd(args)
        elif args.sources_cmd == "show":
            sources_show_cmd(args)
        elif args.sources_cmd == "plan":
            sources_plan_cmd(args)
        elif args.sources_cmd == "schedule":
            sources_schedule_cmd(args)
        elif args.sources_cmd == "harvest":
            sources_harvest_cmd(args)
        elif args.sources_cmd == "runs":
            sources_runs_cmd(args)
        else:
            sources.print_help()
    elif args.command == "analysis":
        if args.analysis_cmd == "catalog":
            analysis_catalog_cmd(args)
        elif args.analysis_cmd == "run":
            analysis_run_cmd(args)
        else:
            analysis.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
