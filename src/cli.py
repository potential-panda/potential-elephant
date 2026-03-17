import argparse
import asyncio
import logging
import os
import random
import sys
from datetime import datetime
from typing import List

import pandas as pd

# Add external path for DtRange
EXTERNAL_UTIL_PATH = "/home/lulurun/workspace/potential-panda-core/src"
if EXTERNAL_UTIL_PATH not in sys.path:
    sys.path.append(EXTERNAL_UTIL_PATH)

try:
    from qate.util.dt_range import DtRange
except ImportError:
    logging.warning("Could not import DtRange. Querying with range might be limited.")
    DtRange = None

from elephant.framework import HarvesterTask, Planner, Scheduler, Store
from elephant.tickers import get_tickers
from elephant.yjp.harvester import YahooFinanceHarvester
from elephant.yjp.planner import YahooFinancePlanner
from elephant.minkabu.harvester import MinkabuHarvester
from elephant.minkabu.planner import MinkabuPlanner

TICKERS_FILE = "tickers.txt"
DATA_DIR = "./data"


class MultiPlanner(Planner):
    def __init__(self, planners: List[Planner]):
        self.planners = planners

    def create(self) -> List[HarvesterTask]:
        all_tasks = []
        for planner in self.planners:
            all_tasks.extend(planner.create())
        return all_tasks


async def fetch_cmd(args):
    selected_tickers = get_tickers(TICKERS_FILE, num=5)
    if not selected_tickers:
        return

    logging.info(f"Selected random tickers for fetch: {selected_tickers}")
    store = Store(DATA_DIR)

    for ticker in selected_tickers:
        try:
            print(f"\n--- Fetching data for {ticker} ---")
            if args.dataset in ["yahoo_comments", "yahoo_evaluations"]:
                harvester = YahooFinanceHarvester(store, ticker)
                await harvester.start({"max_pages": 1, "max_comments": 20})
            elif args.dataset == "minkabu_raw_html":
                harvester = MinkabuHarvester(store, ticker)
                await harvester.start({})
            print(f"Finished fetching {ticker}")
        except Exception:
            logging.exception(f"Failed to fetch {ticker}")


def query_cmd(args):
    """Execute a query against the stored datasets."""
    ticker = args.ticker
    if not ticker.endswith(".T"):
        ticker = f"{ticker}.T"

    path_pattern = os.path.join(DATA_DIR, f"dataset={args.dataset}", f"ticker={ticker}", "**", "data.parquet")
    import glob
    files = glob.glob(path_pattern, recursive=True)

    if not files:
        print(f"No data found for {ticker} in {args.dataset}.")
        return

    dfs = []
    for f in files:
        try:
            dfs.append(pd.read_parquet(f))
        except Exception as e:
            logging.warning(f"Failed to read {f}: {e}")
    
    if not dfs:
        print("Failed to load any data.")
        return
        
    df = pd.concat(dfs, ignore_index=True)

    if args.start:
        if DtRange:
            try:
                dt_range = DtRange.from_strings(args.start, args.end)
                target_days = dt_range.days
                
                # Check column for date filtering
                if args.dataset == "yahoo_comments":
                    df["date_tmp"] = pd.to_datetime(df["scraped_at"]).dt.strftime("%Y-%m-%d")
                    df = df[df["date_tmp"].isin(target_days)]
                elif args.dataset in ["yahoo_evaluations", "minkabu_raw_html"]:
                    # Both use YEAR partitioning, but we can filter by exact date using scraped_at
                    df["date_tmp"] = pd.to_datetime(df["scraped_at"]).dt.strftime("%Y-%m-%d")
                    df = df[df["date_tmp"].isin(target_days)]
            except Exception as e:
                print(f"Error processing date range: {e}")

    if args.dataset == "yahoo_comments":
        if "post_datetime" in df.columns:
            df["post_datetime_dt"] = pd.to_datetime(df["post_datetime"])
            df = df.sort_values(by=["post_datetime_dt", "post_id"], ascending=[False, False])
        
        if not args.start and not args.end:
            df = df.head(200)
        
        if not df.empty:
            print(f"\n--- Top {len(df)} comments for {ticker} ---")
            for _, row in df.iterrows():
                print(f"[{row['post_datetime']}] (ID: {row['post_id']}) {row['author']}: {row['body'][:150]}...")
        else:
            print("No comments match the query.")
    elif args.dataset == "minkabu_raw_html":
        df = df.sort_values(by="scraped_at", ascending=False)
        if not df.empty:
            latest = df.iloc[0]
            print(f"\n--- Latest Minkabu Data for {ticker} ({latest['scraped_at']}) ---")
            for field in ["analysis", "research", "pick", "analyst_consensus"]:
                content = latest.get(field, "")
                print(f"\n[{field.upper()}] (length: {len(content)})")
                print(content[:500] + "..." if len(content) > 500 else content)
        else:
            print("No Minkabu data found.")
    else:
        df = df.sort_values(by="scraped_at", ascending=False)
        print(df.head(20))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Yahoo Japan Finance BBS Scraper CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch data for 5 random stocks (testing)")
    fetch_parser.add_argument(
        "--dataset", choices=["yahoo_comments", "yahoo_evaluations", "minkabu_raw_html"], 
        required=True, help="Target dataset to display"
    )

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Schedule or dry-run daily scraping")
    schedule_parser.add_argument("--dry-run", action="store_true", help="Print the plan and exit")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query the stored dataset")
    query_parser.add_argument("--dataset", choices=["yahoo_comments", "yahoo_evaluations", "minkabu_raw_html"], required=True)
    query_parser.add_argument("--ticker", required=True)
    query_parser.add_argument("--start", help="Start date (YYYY-MM-DD or YYYYMMDD)")
    query_parser.add_argument("--end", help="End date (YYYY-MM-DD or YYYYMMDD)")

    args = parser.parse_args()

    if args.command == "fetch":
        asyncio.run(fetch_cmd(args))
    elif args.command == "query":
        query_cmd(args)
    elif args.command == "schedule":
        store = Store(DATA_DIR)
        
        yjp_planner = YahooFinancePlanner(store, TICKERS_FILE)
        minkabu_planner = MinkabuPlanner(store, TICKERS_FILE)
        
        multi_planner = MultiPlanner([yjp_planner, minkabu_planner])
        scheduler = Scheduler(multi_planner)
        
        if args.dry_run:
            tasks = multi_planner.create()
            print("--- Daily Execution Plan (Dry Run) ---")
            tasks.sort(key=lambda x: x.scheduled_at)
            for task in tasks:
                ticker = task.harvester.ticker
                source = "YJP" if isinstance(task.harvester, YahooFinanceHarvester) else "Minkabu"
                print(f"{task.scheduled_at.strftime('%H:%M')} - {ticker} ({source})")
            print(f"Total tasks: {len(tasks)}")
        else:
            scheduler.start()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
