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
from elephant.source.tickers import all_known_tickers, known_tickers
from elephant.ticker_registry import normalize_ticker
from elephant.analysis.catalog import list_data
from elephant.analysis.pipeline import analyze_ticker, save_analysis
from elephant.analysis.batch import run_daily_analysis
from elephant.theme.apply import apply_river_suggestions
from elephant.theme.builder import build_theme_river_system
from elephant.theme.catalog import list_theme_sources
from elephant.theme.harvest import harvest_theme_sources
from elephant.theme.io import import_etf_holdings_csv, import_theme_members_csv, load_river_suggestions, load_theme_source_themes, load_ticker_theme_scores


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
        tickers = all_known_tickers()
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


def analysis_batch_cmd(args):
    result = run_daily_analysis(limit=args.limit)
    print(
        f"analysis batch requested={result.requested} analyzed={result.analyzed} "
        f"failed={result.failed} started={result.started_at} finished={result.finished_at}"
    )
    for error in result.errors:
        print(f"  failed {error['ticker']}: {error['error']}")


def themes_import_members_cmd(args):
    rows = import_theme_members_csv(args.csv)
    print(f"Imported {rows} theme member rows")


def themes_sources_cmd(args):
    sources = list_theme_sources(enabled_only=not args.all)
    for source in sources:
        url = source.url or "-"
        print(
            f"{source.source_id:<22} {source.kind:<12} {source.theme_id:<24} "
            f"extractor={source.extractor:<18} url={url}"
        )


def themes_harvest_sources_cmd(args):
    results = harvest_theme_sources(source_id=args.source)
    for result in results:
        print(
            f"{result['source_id']:<22} {result['kind']:<12} "
            f"dataset={result['dataset']:<14} rows={result['rows']}"
        )


def themes_import_etf_cmd(args):
    rows = import_etf_holdings_csv(args.csv)
    print(f"Imported {rows} ETF holding rows")


def themes_build_cmd(args):
    result = build_theme_river_system(save=args.save)
    print(
        f"theme build score_rows={result.score_rows} suggestion_rows={result.suggestion_rows} "
        f"generated_at={result.generated_at}"
    )


def themes_scores_cmd(args):
    df = load_ticker_theme_scores()
    if df.empty:
        print("No ticker theme scores found. Run `themes build --save` first.")
        return
    df = df.sort_values(["score", "evidence_count"], ascending=[False, False]).head(args.limit)
    for _, row in df.iterrows():
        print(
            f"{row.get('ticker',''):<10} {row.get('theme_id',''):<26} "
            f"score={float(row.get('score') or 0):>6.2f} evidence={int(row.get('evidence_count') or 0):<3} "
            f"river={row.get('river_id','')}"
        )


def themes_source_themes_cmd(args):
    df = load_theme_source_themes()
    if df.empty:
        print("No raw source themes found. Run `themes harvest-sources` first.")
        return
    df = df.sort_values(["source_id", "rank"], ascending=[True, True]).head(args.limit)
    for _, row in df.iterrows():
        print(
            f"{row.get('source_id',''):<24} rank={int(row.get('rank') or 0):<3} "
            f"canonical={row.get('canonical_theme_id','') or '-':<26} "
            f"theme={row.get('source_theme_name','')}"
        )


def themes_suggestions_cmd(args):
    df = load_river_suggestions()
    if df.empty:
        print("No river suggestions found. Run `themes build --save` first.")
        return
    if not args.include_existing and "status" in df.columns:
        df = df[df["status"] != "existing"]
    df = df.sort_values(["score"], ascending=False).head(args.limit)
    for _, row in df.iterrows():
        print(
            f"{row.get('ticker',''):<10} {row.get('status',''):<9} {row.get('river_id',''):<14} "
            f"{row.get('layer',''):<7} score={float(row.get('score') or 0):>6.2f} "
            f"theme={row.get('theme_id','')}"
        )


def themes_apply_cmd(args):
    result = apply_river_suggestions(
        min_score=args.min_score,
        remove_min_score=args.remove_min_score,
        remove_low_score=not args.keep_low_score,
        suggestion_id=args.suggestion_id,
        dry_run=args.dry_run,
    )
    mode = "dry-run" if result.dry_run else "applied"
    print(
        f"theme apply {mode} evaluated={result.evaluated} applied={result.applied} "
        f"removed={result.removed} skipped={result.skipped}"
    )
    for change in result.changes[: args.limit]:
        if change["action"] == "add_node":
            print(
                f"  add {change['ticker']} -> {change['river_id']}[{change['layer']}] "
                f"score={change['score']:.2f} confidence={change['confidence']}"
            )
        elif change["action"] == "remove_node":
            print(
                f"  remove {change['ticker']} from {change['river_id']} "
                f"score={change['score']:.2f} reason={change['reason']}"
            )
        else:
            print(f"  skip {change.get('ticker','')} reason={change.get('reason','')}")


def main():
    parser = argparse.ArgumentParser(description="Potential Elephant v2 CLI")
    subparsers = parser.add_subparsers(dest="command")

    sources = subparsers.add_parser("sources", help="Source component commands")
    source_subs = sources.add_subparsers(dest="sources_cmd")

    analysis = subparsers.add_parser("analysis", help="Analysis component commands")
    analysis_subs = analysis.add_subparsers(dest="analysis_cmd")

    themes = subparsers.add_parser("themes", help="Build theme evidence and river suggestions")
    theme_subs = themes.add_subparsers(dest="themes_cmd")

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

    analysis_batch = analysis_subs.add_parser("batch", help="Analyze known tickers and save analysis datasets")
    analysis_batch.add_argument("--limit", type=int, help="Limit number of tickers for testing")

    theme_members = theme_subs.add_parser("import-members", help="Import theme member CSV")
    theme_members.add_argument("--csv", required=True)

    theme_etf = theme_subs.add_parser("import-etf", help="Import ETF holdings CSV")
    theme_etf.add_argument("--csv", required=True)

    theme_sources = theme_subs.add_parser("sources", help="List configured theme/ETF source links")
    theme_sources.add_argument("--all", action="store_true", help="Include disabled sources")

    theme_harvest_sources = theme_subs.add_parser("harvest-sources", help="Harvest configured source links")
    theme_harvest_sources.add_argument("--source", help="Harvest one source_id")

    theme_build = theme_subs.add_parser("build", help="Build ticker-theme scores and river suggestions")
    theme_build.add_argument("--save", action="store_true", help="Save output datasets")

    theme_scores = theme_subs.add_parser("scores", help="Show latest ticker-theme scores")
    theme_scores.add_argument("--limit", type=int, default=50)

    theme_source_themes = theme_subs.add_parser("source-themes", help="Show latest raw source themes")
    theme_source_themes.add_argument("--limit", type=int, default=50)

    theme_suggestions = theme_subs.add_parser("suggestions", help="Show latest river suggestions")
    theme_suggestions.add_argument("--limit", type=int, default=50)
    theme_suggestions.add_argument("--include-existing", action="store_true")

    theme_apply = theme_subs.add_parser("apply", help="Apply saved river suggestions to river_tree.json")
    theme_apply.add_argument("--min-score", type=float, default=30.0)
    theme_apply.add_argument("--remove-min-score", type=float, default=28.0)
    theme_apply.add_argument(
        "--keep-low-score",
        action="store_true",
        help="Do not remove theme-discovered tree nodes whose latest score is below remove-min-score",
    )
    theme_apply.add_argument("--suggestion-id")
    theme_apply.add_argument("--dry-run", action="store_true", help="Preview changes without editing the tree")
    theme_apply.add_argument("--limit", type=int, default=50, help="Limit printed changes")

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
        elif args.analysis_cmd == "batch":
            analysis_batch_cmd(args)
        else:
            analysis.print_help()
    elif args.command == "themes":
        if args.themes_cmd == "import-members":
            themes_import_members_cmd(args)
        elif args.themes_cmd == "import-etf":
            themes_import_etf_cmd(args)
        elif args.themes_cmd == "sources":
            themes_sources_cmd(args)
        elif args.themes_cmd == "harvest-sources":
            themes_harvest_sources_cmd(args)
        elif args.themes_cmd == "build":
            themes_build_cmd(args)
        elif args.themes_cmd == "scores":
            themes_scores_cmd(args)
        elif args.themes_cmd == "source-themes":
            themes_source_themes_cmd(args)
        elif args.themes_cmd == "suggestions":
            themes_suggestions_cmd(args)
        elif args.themes_cmd == "apply":
            themes_apply_cmd(args)
        else:
            themes.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
