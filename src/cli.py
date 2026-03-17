import argparse
import asyncio
import logging
import os
import random
import sys
from datetime import datetime

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

from elephant.framework import Scheduler, Store
from elephant.harvester import YahooFinanceHarvester, YahooFinancePlanner

TICKERS_FILE = "tickers.txt"
DATA_DIR = "./data"


def get_tickers():
    if not os.path.exists(TICKERS_FILE):
        logging.error(f"{TICKERS_FILE} not found.")
        return []
    with open(TICKERS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


async def fetch_cmd(args):
    tickers = get_tickers()
    if not tickers:
        return

    selected_tickers = random.sample(tickers, min(5, len(tickers)))
    logging.info(f"Selected random tickers for fetch: {selected_tickers}")

    store = Store(DATA_DIR)
    harvester = YahooFinanceHarvester(store)

    for ticker in selected_tickers:
        try:
            print(f"Fetching data for {ticker}...")
            # We use a smaller scrape limit for fetch command
            await harvester.start({"ticker": ticker, "max_pages": 1, "max_comments": 20})
            print(f"Finished fetching {ticker}")
        except Exception:
            logging.exception(f"Failed to fetch {ticker}")


def query_cmd(args):
    """Execute a query against the stored datasets."""
    ticker = args.ticker
    if not ticker.endswith(".T"):
        ticker = f"{ticker}.T"

    # In new framework, path is dataset=X/tag1=val1/tag2=val2/data.parquet
    # We use glob to find all parquet files for the ticker
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
                # In framework, yahoo_comments has 'date' tag, yahoo_evaluations has 'date' tag (YEAR)
                if args.dataset == "yahoo_comments":
                    # Filter by scraped_at or derive from it
                    df["date_tmp"] = pd.to_datetime(df["scraped_at"]).dt.strftime("%Y-%m-%d")
                    df = df[df["date_tmp"].isin(target_days)]
                elif args.dataset == "yahoo_evaluations":
                    years = list(set(d[:4] for d in target_days))
                    df["year_tmp"] = pd.to_datetime(df["scraped_at"]).dt.strftime("%Y")
                    df = df[df["year_tmp"].isin(years)]
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
        "--dataset", choices=["yahoo_comments", "yahoo_evaluations"], required=True, help="Target dataset to display"
    )

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Schedule or dry-run daily scraping")
    schedule_parser.add_argument("--dry-run", action="store_true", help="Print the plan and exit")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query the stored dataset")
    query_parser.add_argument("--dataset", choices=["yahoo_comments", "yahoo_evaluations"], required=True)
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
        harvester = YahooFinanceHarvester(store)
        planner = YahooFinancePlanner(harvester, TICKERS_FILE)
        scheduler = Scheduler(planner)
        
        if args.dry_run:
            tasks = planner.create()
            print("--- Daily Execution Plan (Dry Run) ---")
            tasks.sort(key=lambda x: x.scheduled_at)
            for task in tasks:
                print(f"{task.scheduled_at.strftime('%H:%M')} - {task.args['ticker']}")
            print(f"Total tasks: {len(tasks)}")
        else:
            scheduler.start()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
