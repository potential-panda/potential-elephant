import argparse
import asyncio
import logging
import os
from datetime import datetime
from typing import List

import pandas as pd
from qate.util.dt_range import DtRange

import elephant.secrets as _secrets
from elephant.framework import HarvesterTask, Planner, Scheduler, Store
from elephant.minkabu.harvester import MinkabuHarvester
from elephant.minkabu.planner import MinkabuPlanner
from elephant.news.harvester import NewsHarvester
from elephant.news.planner import NewsPlanner
from elephant.river.discoverer import Discoverer
from elephant.river.seed import SEED_NODES
from elephant.river.tree import FRAMEWORK_RIVERS, RiverTree
from elephant.tickers import get_tickers
from elephant.yjp.harvester import YahooFinanceHarvester
from elephant.yjp.planner import YahooFinancePlanner
from elephant.tdnet.harvester import TDnetHarvester
from elephant.tdnet.planner import TDnetPlanner
from elephant.yjp_bbs_rank.harvester import BbsRankHarvester
from elephant.yjp_bbs_rank.planner import BbsRankPlanner
from elephant.price.planner import PricePlanner

TICKERS_FILE = "/panda-infra/elephant/tickers.txt"
DATA_DIR = "/panda-infra/elephant"
TREE_PATH = os.path.join(DATA_DIR, "river_tree.json")

_secrets.load()


class MultiPlanner(Planner):
    def __init__(self, planners: List[Planner]):
        self.planners = planners

    def create(self) -> List[HarvesterTask]:
        all_tasks = []
        for planner in self.planners:
            all_tasks.extend(planner.create())
        return all_tasks


# --- fetch ---


async def fetch_cmd(args):
    store = Store(DATA_DIR)

    if args.dataset == "yjp_bbs_rank":
        try:
            print("\n--- Fetching BBS ranking tickers ---")
            harvester = BbsRankHarvester(store, TICKERS_FILE)
            await harvester.start({})
            print("Finished fetching BBS ranking")
        except Exception:
            logging.exception("Failed to fetch BBS ranking")
        return

    if args.dataset == "news_headlines":
        try:
            print("\n--- Fetching news headlines ---")
            harvester = NewsHarvester(store)
            await harvester.start({})
            print("Finished fetching news headlines")
        except Exception:
            logging.exception("Failed to fetch news headlines")
        return

    if args.dataset == "tdnet_disclosures":
        try:
            print("\n--- Fetching TDnet disclosures ---")
            harvester = TDnetHarvester(store, lookback_days=1)
            await harvester.start({})
            print("Finished fetching TDnet disclosures")
        except Exception:
            logging.exception("Failed to fetch TDnet disclosures")
        return

    selected_tickers = get_tickers(TICKERS_FILE, num=2)
    if not selected_tickers:
        return

    logging.info(f"Selected random tickers for fetch: {selected_tickers}")

    for ticker in selected_tickers:
        try:
            print(f"\n--- Fetching data for {ticker} ---")
            if args.dataset in ["yahoo_comments", "yahoo_evaluations"]:
                harvester = YahooFinanceHarvester(store, ticker, tickers_file=TICKERS_FILE)
                await harvester.start({"max_pages": 1, "max_comments": 20})
            elif args.dataset == "minkabu_raw_html":
                harvester = MinkabuHarvester(store, ticker)
                await harvester.start({})
            print(f"Finished fetching {ticker}")
        except Exception:
            logging.exception(f"Failed to fetch {ticker}")


# --- query ---


def query_cmd(args):
    import glob

    # --- news_headlines: date-partitioned, no ticker ---
    if args.dataset == "news_headlines":
        pattern = os.path.join(DATA_DIR, "dataset=news_headlines", "date=*", "data.parquet")
        files = sorted(glob.glob(pattern), reverse=True)
        if not files:
            print("No news data found. Run: python src/cli.py fetch --dataset news_headlines")
            return

        dfs = []
        for f in files:
            try:
                dfs.append(pd.read_parquet(f))
            except Exception as e:
                logging.warning(f"Failed to read {f}: {e}")

        df = pd.concat(dfs, ignore_index=True)
        df["scraped_at"] = pd.to_datetime(df["scraped_at"])
        df = df.sort_values("scraped_at", ascending=False)

        if args.keyword:
            mask = df["title"].str.contains(args.keyword, case=False, na=False)
            if "summary" in df.columns:
                mask |= df["summary"].fillna("").str.contains(args.keyword, case=False, na=False)
            df = df[mask]
            print(f"\n--- News matching '{args.keyword}' ---")
        else:
            df = df.head(args.limit if hasattr(args, "limit") else 50)
            print(f"\n--- Latest {len(df)} news items ---")

        if df.empty:
            print("No matching news found.")
            return

        import re as _re
        for _, row in df.iterrows():
            date = pd.to_datetime(row["scraped_at"]).strftime("%Y-%m-%d")
            source = row.get("source", "")
            title = row.get("title", "")
            raw_summary = row.get("summary") or ""
            summary = _re.sub(r"<[^>]+>", "", raw_summary)
            summary = _re.sub(r"&[a-z]+;", " ", summary).strip()[:120]
            print(f"[{date}] [{source}] {title}")
            if summary:
                print(f"  {summary}")
        return

    # --- ticker-based datasets ---
    ticker = args.ticker
    if not ticker:
        print("--ticker is required for this dataset.")
        return
    from elephant.ticker_registry import normalize_ticker
    ticker = normalize_ticker(ticker)

    path_pattern = os.path.join(DATA_DIR, f"dataset={args.dataset}", f"ticker={ticker}", "**", "data.parquet")
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
                df["date_tmp"] = pd.to_datetime(df["scraped_at"]).dt.strftime("%Y-%m-%d")
                df = df[df["date_tmp"].isin(target_days)]
            except Exception as e:
                print(f"Error processing date range: {e}")

    if args.dataset == "yahoo_comments":
        if "post_datetime" in df.columns:
            df["post_datetime_dt"] = pd.to_datetime(df["post_datetime"])
            df = df.sort_values(by=["post_datetime_dt", "post_id"], ascending=[False, False])
        if not args.start and not args.end:
            df = df.head(500)
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


# --- digest ---


def digest_cmd(args):
    from elephant.synthesizer import Synthesizer

    tree = RiverTree(TREE_PATH)
    synthesizer = Synthesizer(DATA_DIR, TICKERS_FILE, tree=tree)
    logging.info("Generating digest...")
    digest = synthesizer.generate()

    print("\n" + digest)

    digests_dir = os.path.join(DATA_DIR, "digests")
    os.makedirs(digests_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")

    output_path = os.path.join(digests_dir, f"{date_str}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(digest)
    logging.info(f"Digest saved to {output_path}")

    from elephant.formatter import to_html

    html_path = os.path.join(digests_dir, f"{date_str}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(to_html(digest))
    logging.info(f"HTML digest saved to {html_path}")

    from elephant.notifier import send as notify

    notify(digest)


# --- tickers ---


def tickers_cmd(args):
    import glob
    from datetime import timedelta

    from elephant.ticker_registry import load_cache

    days = args.days
    since = datetime.now() - timedelta(days=days)
    datasets = ["yahoo_comments", "yahoo_evaluations", "minkabu_raw_html"]

    # ticker -> {dataset -> latest scraped_at}
    ticker_data: dict[str, dict] = {}

    for dataset in datasets:
        pattern = os.path.join(DATA_DIR, f"dataset={dataset}", "ticker=*", "**", "data.parquet")
        for f in glob.glob(pattern, recursive=True):
            ticker = f.split(f"dataset={dataset}/ticker=")[1].split("/")[0]
            try:
                df = pd.read_parquet(f, columns=["scraped_at"])
                df["scraped_at"] = pd.to_datetime(df["scraped_at"])
                latest = df["scraped_at"].max()
                if latest >= since:
                    if ticker not in ticker_data:
                        ticker_data[ticker] = {}
                    prev = ticker_data[ticker].get(dataset)
                    if prev is None or latest > prev:
                        ticker_data[ticker][dataset] = latest
            except Exception:
                pass

    if not ticker_data:
        print(f"No tickers with data in the last {days} days.")
        return

    # Load speed history from registry
    registry = load_cache(TICKERS_FILE)

    # sort by most recently active
    sorted_tickers = sorted(
        ticker_data.items(),
        key=lambda x: max(x[1].values()),
        reverse=True,
    )

    ds_short = {"yahoo_comments": "comments", "yahoo_evaluations": "eval", "minkabu_raw_html": "minkabu"}
    print(f"\n{'Ticker':<12} {'Last Active':<14} {'Speed (c/h)':<14} {'Datasets'}")
    print("-" * 70)
    for ticker, ds_map in sorted_tickers:
        last = max(ds_map.values()).strftime("%Y-%m-%d")
        datasets_str = "  ".join(
            f"{ds_short[d]}({ds_map[d].strftime('%m-%d')})" for d in datasets if d in ds_map
        )
        entry = registry.get(ticker, {})
        history = entry.get("speed_history", []) if isinstance(entry, dict) else []
        if history:
            recent = history[0]
            speed_str = f"{recent['comments_per_hour']:.1f} ({recent['date'][5:]})"
        else:
            speed_str = "-"
        print(f"{ticker:<12} {last:<14} {speed_str:<14} {datasets_str}")

    print(f"\nTotal: {len(sorted_tickers)} tickers with data in the last {days} days.")


# --- dive ---


def dive_cmd(args):
    from elephant.diver import Diver
    from elephant.formatter import to_html

    ticker = args.ticker
    tree = RiverTree(TREE_PATH)
    diver = Diver(DATA_DIR, tree=tree)

    logging.info(f"Diving into {ticker}...")
    brief = diver.dive(ticker)

    print("\n" + brief)

    dives_dir = os.path.join(DATA_DIR, "dives")
    os.makedirs(dives_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = ticker.replace(".", "_")

    md_path = os.path.join(dives_dir, f"{date_str}-{slug}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(brief)

    html_path = os.path.join(dives_dir, f"{date_str}-{slug}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(to_html(brief))

    logging.info(f"Dive saved to {md_path}")

    from elephant.formatter import to_markdown
    from elephant.notifier import send as notify

    notify(to_markdown(brief))


# --- tree ---


def tree_cmd(args):
    tree = RiverTree(TREE_PATH)

    if args.tree_cmd == "show":
        print(tree.to_display(river_id=getattr(args, "river", None)))

    elif args.tree_cmd == "init":
        existing_rivers = {r.id for r in tree.list_rivers()}
        added_rivers, added_nodes = [], []

        for r in FRAMEWORK_RIVERS:
            if r["id"] not in existing_rivers:
                tree.add_river(r["id"], r["name"], r.get("description", ""))
                added_rivers.append(r["name"])

            # Populate nodes from seed data
            river_obj = tree.get_river(r["id"])
            existing_tickers = {n.ticker for n in (river_obj.nodes if river_obj else [])}
            for node in SEED_NODES.get(r["id"], []):
                if node["ticker"] not in existing_tickers:
                    try:
                        tree.add_node(
                            river_id=r["id"],
                            ticker=node["ticker"],
                            layer=node["layer"],
                            name=node.get("name", ""),
                            market=node.get("market", "US"),
                            role=node.get("role", ""),
                            source="seed",
                        )
                        added_nodes.append(f"{node['ticker']} ({r['id']})")
                    except ValueError:
                        pass  # already exists

        if added_rivers:
            print(f"Added rivers: {', '.join(added_rivers)}")
        if added_nodes:
            print(f"Added {len(added_nodes)} nodes from V1 ticker matrix")
        if not added_rivers and not added_nodes:
            print("River tree already up to date.")
        print(tree.to_display())

    elif args.tree_cmd == "river-add":
        try:
            tree.add_river(args.id, args.name, getattr(args, "description", "") or "")
            print(f"Added river: [{args.id}] {args.name}")
        except ValueError as e:
            print(f"Error: {e}")

    elif args.tree_cmd == "river-remove":
        if tree.remove_river(args.id):
            print(f"Removed river: {args.id}")
        else:
            print(f"River not found: {args.id}")

    elif args.tree_cmd == "node-add":
        try:
            node = tree.add_node(
                river_id=args.river,
                ticker=args.ticker,
                layer=args.layer,
                name=getattr(args, "name", "") or "",
                market=getattr(args, "market", "US") or "US",
                role=getattr(args, "role", "") or "",
                notes=getattr(args, "notes", "") or "",
            )
            print(f"Added node: {node.ticker} [{node.layer}] to river '{args.river}'")
        except ValueError as e:
            print(f"Error: {e}")

    elif args.tree_cmd == "node-update":
        kwargs = {
            k: v for k, v in vars(args).items() if k in ("layer", "name", "market", "role", "notes") and v is not None
        }
        if tree.update_node(args.river, args.ticker, **kwargs):
            print(f"Updated {args.ticker} in river '{args.river}'")
        else:
            print(f"Node not found: {args.ticker} in river '{args.river}'")

    elif args.tree_cmd == "node-remove":
        if tree.remove_node(args.river, args.ticker):
            print(f"Removed {args.ticker} from river '{args.river}'")
        else:
            print(f"Node not found: {args.ticker} in river '{args.river}'")

    elif args.tree_cmd == "news-add":
        tree.add_news(
            ticker=args.ticker,
            title=args.title,
            url=args.url,
            source=args.source,
            date=getattr(args, "date", None),
        )
        print(f"Added news for {args.ticker}: {args.title[:60]}")

    else:
        print("Unknown tree command.")
        print("Use: show, init, river-add, river-remove, node-add, node-update, node-remove, news-add")


# --- discover ---


def discover_cmd(args):
    tree = RiverTree(TREE_PATH)
    discoverer = Discoverer(DATA_DIR, TICKERS_FILE, tree)

    if args.ticker:
        # Classify a specific ticker
        print(f"Classifying {args.ticker}...")
        result = discoverer.classify_ticker(args.ticker)
        _print_suggestion(result)
        if (
            result
            and args.auto
            and result.get("fits_existing_river")
            and result.get("confidence") in ("high", "medium")
        ):
            _auto_add(tree, result)

    elif args.keyword:
        # Keyword search → extract tickers → classify
        print(f"Searching for tickers related to: '{args.keyword}'...")
        results = discoverer.classify_keyword(args.keyword)
        for result in results:
            _print_suggestion(result)
            if args.auto and result.get("fits_existing_river") and result.get("confidence") in ("high", "medium"):
                _auto_add(tree, result)

    else:
        # Autonomous scan of BBS unknowns
        print("Scanning BBS hot tickers not yet in the river tree...")
        suggestions = discoverer.scan_unknown_tickers()
        if not suggestions:
            print("No high-confidence suggestions found.")
            return
        for result in suggestions:
            _print_suggestion(result)
            if args.auto and result.get("fits_existing_river") and result.get("confidence") in ("high", "medium"):
                _auto_add(tree, result)
            elif not args.auto:
                answer = input("Add to tree? [y/n/skip] ").strip().lower()
                if answer == "y":
                    _auto_add(tree, result)


def _print_suggestion(result: dict) -> None:
    if not result:
        print("(no classification returned)")
        return
    confidence = result.get("confidence", "?")
    fits = result.get("fits_existing_river", False)
    print(f"\n[SUGGESTION — {confidence} confidence]")
    print(f"Ticker:  {result.get('ticker')} ({result.get('market', '?')})")
    if fits:
        print(f"River:   {result.get('river_id')}")
        print(f"Layer:   {result.get('layer')}")
    else:
        new_river = result.get("new_river_name")
        print(
            f"River:   (new river suggested: {new_river})" if new_river else "River:   (does not fit any known river)"
        )
    print(f"Name:    {result.get('name', '')}")
    print(f"Role:    {result.get('role', '')}")
    print(f"Reason:  {result.get('reasoning', '')}")


def _auto_add(tree: RiverTree, result: dict) -> None:
    try:
        node = tree.add_node(
            river_id=result["river_id"],
            ticker=result["ticker"],
            layer=result["layer"],
            name=result.get("name", ""),
            market=result.get("market", "US"),
            role=result.get("role", ""),
            source="discovery",
        )
        print(f"  -> Added {node.ticker} [{node.layer}] to river '{result['river_id']}'")
    except ValueError as e:
        print(f"  -> Could not add: {e}")


# --- schedule ---


def schedule_cmd(args):
    store = Store(DATA_DIR)

    bbs_rank_planner = BbsRankPlanner(store, TICKERS_FILE)
    yjp_planner = YahooFinancePlanner(store, TICKERS_FILE, tree_path=TREE_PATH)
    minkabu_planner = MinkabuPlanner(store, TICKERS_FILE, tree_path=TREE_PATH)
    news_planner = NewsPlanner(store)
    tdnet_planner = TDnetPlanner(store)
    price_planner = PricePlanner(store, TICKERS_FILE, tree_path=TREE_PATH)

    multi_planner = MultiPlanner([bbs_rank_planner, yjp_planner, minkabu_planner, news_planner, tdnet_planner, price_planner])
    scheduler = Scheduler(multi_planner)

    if args.dry_run:
        tasks = multi_planner.create()
        print("--- Daily Execution Plan (Dry Run) ---")
        tasks.sort(key=lambda x: x.scheduled_at)
        for task in tasks:
            if isinstance(task.harvester, YahooFinanceHarvester):
                label = f"{task.harvester.ticker} (YJP)"
            elif isinstance(task.harvester, MinkabuHarvester):
                label = f"{task.harvester.ticker} (Minkabu)"
            elif isinstance(task.harvester, NewsHarvester):
                label = "News Headlines (RSS)"
            elif isinstance(task.harvester, TDnetHarvester):
                label = "TDnet Disclosures"
            else:
                label = "BBS Rank Update"
            print(f"{task.scheduled_at.strftime('%H:%M')} - {label}")
        print(f"Total tasks: {len(tasks)}")
    else:
        scheduler.start()


# --- main ---


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Potential Elephant CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Fetch data for testing")
    fetch_parser.add_argument(
        "--dataset",
        choices=["yahoo_comments", "yahoo_evaluations", "minkabu_raw_html", "yjp_bbs_rank", "news_headlines", "tdnet_disclosures"],
        required=True,
    )

    # query
    query_parser = subparsers.add_parser("query", help="Query stored dataset")
    query_parser.add_argument(
        "--dataset",
        choices=["yahoo_comments", "yahoo_evaluations", "minkabu_raw_html", "news_headlines"],
        required=True,
    )
    query_parser.add_argument("--ticker", default=None, help="Ticker (required for BBS/Minkabu datasets)")
    query_parser.add_argument("--start")
    query_parser.add_argument("--end")
    query_parser.add_argument("--keyword", default=None, help="Filter news by keyword (news_headlines only)")
    query_parser.add_argument("--limit", type=int, default=50, help="Max items to show (news_headlines only)")

    # digest
    subparsers.add_parser("digest", help="Generate daily research digest")

    # schedule
    schedule_parser = subparsers.add_parser("schedule", help="Run or dry-run the daily scraping scheduler")
    schedule_parser.add_argument("--dry-run", action="store_true")

    # tree
    tree_parser = subparsers.add_parser("tree", help="Manage the river tree knowledge database")
    tree_subs = tree_parser.add_subparsers(dest="tree_cmd")

    tree_show = tree_subs.add_parser("show", help="Display the tree")
    tree_show.add_argument("--river", help="Show a specific river by id")

    tree_subs.add_parser("init", help="Seed the tree with the 4 framework rivers")

    river_add = tree_subs.add_parser("river-add", help="Add a new river")
    river_add.add_argument("--id", required=True)
    river_add.add_argument("--name", required=True)
    river_add.add_argument("--description", default="")

    river_rm = tree_subs.add_parser("river-remove", help="Remove a river")
    river_rm.add_argument("--id", required=True)

    node_add = tree_subs.add_parser("node-add", help="Add a node to a river")
    node_add.add_argument("--river", required=True)
    node_add.add_argument("--ticker", required=True)
    node_add.add_argument("--layer", required=True, choices=["source", "upper", "middle", "lower"])
    node_add.add_argument("--name", default="")
    node_add.add_argument("--market", default="US", choices=["US", "JP"])
    node_add.add_argument("--role", default="")
    node_add.add_argument("--notes", default="")

    node_upd = tree_subs.add_parser("node-update", help="Update a node")
    node_upd.add_argument("--river", required=True)
    node_upd.add_argument("--ticker", required=True)
    node_upd.add_argument("--layer", choices=["source", "upper", "middle", "lower"])
    node_upd.add_argument("--name")
    node_upd.add_argument("--market", choices=["US", "JP"])
    node_upd.add_argument("--role")
    node_upd.add_argument("--notes")

    node_rm = tree_subs.add_parser("node-remove", help="Remove a node")
    node_rm.add_argument("--river", required=True)
    node_rm.add_argument("--ticker", required=True)

    news_add = tree_subs.add_parser("news-add", help="Tag a news item to a ticker")
    news_add.add_argument("--ticker", required=True)
    news_add.add_argument("--title", required=True)
    news_add.add_argument("--url", required=True)
    news_add.add_argument("--source", required=True)
    news_add.add_argument("--date")

    # discover
    discover_parser = subparsers.add_parser("discover", help="Discover and classify tickers into the river tree")
    discover_parser.add_argument("--ticker", help="Classify a specific ticker")
    discover_parser.add_argument("--keyword", help="Search news for keyword and classify found tickers")
    discover_parser.add_argument("--auto", action="store_true", help="Auto-add high-confidence suggestions")

    dive_parser = subparsers.add_parser("dive", help="Deep dive research brief on a single ticker")
    dive_parser.add_argument("--ticker", required=True, help="Ticker to deep dive (e.g. 8105.T or NVDA)")

    tickers_parser = subparsers.add_parser("tickers", help="List tickers with harvested data in the last N days")
    tickers_parser.add_argument("--days", type=int, default=14, help="Lookback window in days (default: 14)")

    args = parser.parse_args()

    if args.command == "fetch":
        asyncio.run(fetch_cmd(args))
    elif args.command == "query":
        query_cmd(args)
    elif args.command == "digest":
        digest_cmd(args)
    elif args.command == "schedule":
        schedule_cmd(args)
    elif args.command == "tree":
        tree_cmd(args)
    elif args.command == "discover":
        discover_cmd(args)
    elif args.command == "dive":
        dive_cmd(args)
    elif args.command == "tickers":
        tickers_cmd(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
