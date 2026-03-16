import argparse
import asyncio
import hashlib
import logging
import os
import random
import time

import pandas as pd
import schedule
from qate.util.dt_range import DtRange

from elephant.harvester import YahooFinanceHarvester

TICKERS_FILE = "tickers.txt"
DATA_DIR = "./data"
EVAL_DIR = os.path.join(DATA_DIR, "dataset=yahoo_evaluations")
COMMENTS_DIR = os.path.join(DATA_DIR, "dataset=yahoo_comments")


def generate_id(*args):
    content = "|".join(str(arg) for arg in args)
    return hashlib.md5(content.encode()).hexdigest()


async def scrape_ticker_task(ticker: str, max_pages=10, max_comments=200):
    """Core scraping logic for a single ticker."""
    if not ticker.endswith(".T"):
        ticker = f"{ticker}.T"

    logging.info(f"Starting scrape for {ticker}...")
    harvester = YahooFinanceHarvester(ticker)

    # Per-ticker start jitter is handled by the scheduler,
    # but harvester still has internal jitter for pagination.
    evaluation, comments = await harvester.scrape(max_pages=max_pages, max_comments=max_comments)

    if evaluation or comments:
        save_to_duckdb([evaluation] if evaluation else [], comments if comments else [])
        logging.info(f"Successfully scraped and saved {ticker}.")
    else:
        logging.warning(f"No data found for {ticker}.")


def save_to_duckdb(eval_data: list, comments_data: list):
    """Saves scraped data to partitioned Parquet files."""
    if eval_data:
        df_eval = pd.DataFrame(eval_data)
        df_eval["scraped_at"] = pd.to_datetime(df_eval["scraped_at"])
        df_eval["id"] = df_eval.apply(lambda r: generate_id(r["ticker"], r["scraped_at"].strftime("%Y-%m-%d")), axis=1)
        for col in ["strongest", "strong", "both", "weak", "weakest"]:
            if col not in df_eval.columns:
                df_eval[col] = 0.0
        df_eval["YEAR"] = df_eval["scraped_at"].apply(lambda x: x.strftime("%Y")).astype(str)
        df_eval["ticker"] = df_eval["ticker"].astype(str)

        for ticker in df_eval["ticker"].unique():
            ticker_df = df_eval[df_eval["ticker"] == ticker]
            for year in ticker_df["YEAR"].unique():
                year_df = ticker_df[ticker_df["YEAR"] == year]
                target_path = os.path.join(EVAL_DIR, f"ticker={ticker}", f"YEAR={year}")
                os.makedirs(target_path, exist_ok=True)
                file_path = os.path.join(target_path, "data.parquet")
                if os.path.exists(file_path):
                    existing_df = pd.read_parquet(file_path)
                    combined_df = pd.concat([existing_df, year_df]).drop_duplicates(subset=["id"], keep="last")
                    combined_df.to_parquet(file_path, index=False)
                else:
                    year_df.to_parquet(file_path, index=False)

    if comments_data:
        df_comments = pd.DataFrame(comments_data)
        df_comments["scraped_at"] = pd.to_datetime(df_comments["scraped_at"])
        df_comments["id"] = df_comments.apply(
            lambda r: generate_id(r["ticker"], r["post_id"], r["author"], r["post_datetime"]), axis=1
        )
        df_comments["date"] = df_comments["scraped_at"].apply(lambda x: x.strftime("%Y-%m-%d")).astype(str)
        df_comments["ticker"] = df_comments["ticker"].astype(str)

        for ticker in df_comments["ticker"].unique():
            ticker_df = df_comments[df_comments["ticker"] == ticker]
            for d in ticker_df["date"].unique():
                date_df = ticker_df[ticker_df["date"] == d]
                target_path = os.path.join(COMMENTS_DIR, f"ticker={ticker}", f"date={d}")
                os.makedirs(target_path, exist_ok=True)
                file_path = os.path.join(target_path, "data.parquet")
                if os.path.exists(file_path):
                    existing_df = pd.read_parquet(file_path)
                    if "date" in existing_df.columns:
                        existing_df["date"] = existing_df["date"].astype(str)
                    if "ticker" in existing_df.columns:
                        existing_df["ticker"] = existing_df["ticker"].astype(str)
                    combined_df = pd.concat([existing_df, date_df]).drop_duplicates(subset=["id"], keep="last")
                    combined_df.to_parquet(file_path, index=False)
                else:
                    date_df.to_parquet(file_path, index=False)


def get_tickers():
    if not os.path.exists(TICKERS_FILE):
        logging.error(f"{TICKERS_FILE} not found.")
        return []
    with open(TICKERS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


def generate_plan():
    """Generates a randomized execution plan for the current day."""
    tickers = get_tickers()
    if not tickers:
        return []

    random.shuffle(tickers)
    plan = []

    # Time range: 10:17 (617 mins) to 12:23 (743 mins)
    start_min = 10 * 60 + 17
    end_min = 12 * 60 + 23

    for ticker in tickers:
        random_min = random.randint(start_min, end_min)
        scheduled_time = f"{random_min // 60:02d}:{random_min % 60:02d}"
        plan.append({"ticker": ticker, "time": scheduled_time})

    # Sort plan by time for display
    plan.sort(key=lambda x: x["time"])
    return plan


def run_scrape_wrapper(ticker):
    """Synchronous wrapper to run the async scrape task."""
    try:
        asyncio.run(scrape_ticker_task(ticker))
    except Exception:
        logging.exception(f"Failed to execute scheduled scrape for {ticker}")


def schedule_daily_plan():
    """Clear existing jobs and schedule the new daily plan."""
    logging.info("Generating and scheduling daily plan...")
    schedule.clear("daily-scrapes")
    plan = generate_plan()

    for item in plan:
        schedule.every().day.at(item["time"]).do(run_scrape_wrapper, ticker=item["ticker"]).tag("daily-scrapes")

    logging.info(f"Scheduled {len(plan)} tickers for today.")


async def fetch_cmd(args):
    tickers = get_tickers()
    if not tickers:
        return

    selected_tickers = random.sample(tickers, min(5, len(tickers)))
    logging.info(f"Selected random tickers for fetch: {selected_tickers}")

    for ticker in selected_tickers:
        try:
            await scrape_ticker_task(ticker, max_pages=5, max_comments=100)
            # Fetch-specific display logic could go here,
            # but scrape_ticker_task handles the core work.
            print(f"Finished fetching {ticker}")
        except Exception:
            logging.exception(f"Failed to fetch {ticker}")


def query_cmd(args):
    """Execute a query against the stored datasets."""
    ticker = args.ticker
    if not ticker.endswith(".T"):
        ticker = f"{ticker}.T"

    if args.dataset == "yahoo_comments":
        base_dir = COMMENTS_DIR
    elif args.dataset == "yahoo_evaluations":
        base_dir = EVAL_DIR
    else:
        print(f"Unsupported dataset: {args.dataset}")
        return

    # Find all parquet files for this ticker
    path_pattern = os.path.join(base_dir, f"ticker={ticker}", "**", "data.parquet")
    import glob

    files = glob.glob(path_pattern, recursive=True)

    if not files:
        print(f"No data found for {ticker} in {args.dataset}.")
        return

    # Load and combine data
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

    # Filtering by date range if specified
    if args.start:
        if DtRange:
            try:
                dt_range = DtRange.from_strings(args.start, args.end)
                target_days = dt_range.days

                if args.dataset == "yahoo_comments":
                    # Filter by date partition column or derived date
                    if "date" in df.columns:
                        df = df[df["date"].isin(target_days)]
                    else:
                        df["date_tmp"] = pd.to_datetime(df["scraped_at"]).dt.strftime("%Y-%m-%d")
                        df = df[df["date_tmp"].isin(target_days)]
                elif args.dataset == "yahoo_evaluations":
                    years = list(set(d[:4] for d in target_days))
                    if "YEAR" in df.columns:
                        df = df[df["YEAR"].astype(str).isin(years)]
            except Exception as e:
                print(f"Error processing date range: {e}")
        else:
            print("DtRange utility not available. Filtering might be incorrect.")

    # Sorting and limiting
    if args.dataset == "yahoo_comments":
        if "post_datetime" in df.columns:
            df["post_datetime_dt"] = pd.to_datetime(df["post_datetime"])
            # Sort by time then post_id descending
            df = df.sort_values(by=["post_datetime_dt", "post_id"], ascending=[False, False])

        # Logic for limits:
        # 1. No start, no end -> Top 200
        # 2. Start only -> All for that date (already filtered by DtRange)
        # 3. Start and end -> All in range (already filtered by DtRange)
        if not args.start and not args.end:
            df = df.head(200)

        if not df.empty:
            print(f"\n--- Top {len(df)} comments for {ticker} ---")
            for _, row in df.iterrows():
                print(f"[{row['post_datetime']}] (ID: {row['post_id']}) {row['author']}: {row['body'][:150]}...")
        else:
            print("No comments match the query.")

    elif args.dataset == "yahoo_evaluations":
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
        if args.dry_run:
            plan = generate_plan()
            print("--- Daily Execution Plan (Dry Run) ---")
            for item in plan:
                print(f"{item['time']} - {item['ticker']}")
            print(f"Total tickers: {len(plan)}")
        else:
            logging.info("Starting long-running scheduler process...")
            # Schedule the re-generation of the plan every day at 01:00
            schedule.every().day.at("01:00").do(schedule_daily_plan)

            while True:
                schedule.run_pending()
                time.sleep(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
