import argparse
import asyncio
import logging
import os
from datetime import datetime
from typing import List

import pandas as pd
from qate.util.dt_range import DtRange

import elephant.secrets as _secrets
from elephant.config import DATA_DIR, SOURCE_REGISTRY_FILE, TICKERS_FILE, ATLAS_PATH
from elephant.framework import HarvesterTask, Planner, Scheduler, Store
from elephant.minkabu.harvester import MinkabuHarvester
from elephant.minkabu.planner import MinkabuPlanner
from elephant.news.harvester import NewsHarvester
from elephant.news.planner import NewsPlanner
from elephant.atlas.discoverer import Discoverer
from elephant.atlas.seed import SEED_NODES
from elephant.atlas.atlas import FRAMEWORK_VALUE_CHAINS, Atlas
from elephant.source_check import SourceAvailabilityHarvester, SourceAvailabilityPlanner
from elephant.tickers import get_tickers
from elephant.yjp.harvester import YahooFinanceHarvester
from elephant.yjp.planner import YahooFinancePlanner
from elephant.tdnet.harvester import TDnetHarvester
from elephant.tdnet.planner import TDnetPlanner
from elephant.yjp_bbs_rank.harvester import BbsRankHarvester
from elephant.yjp_bbs_rank.planner import BbsRankPlanner
from elephant.price.planner import PricePlanner

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
            if "ticker" in df.columns:
                mask |= df["ticker"].fillna("").str.contains(args.keyword, case=False, na=False)
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

    atlas = Atlas(ATLAS_PATH)
    synthesizer = Synthesizer(DATA_DIR, TICKERS_FILE, atlas=atlas)
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
    atlas = Atlas(ATLAS_PATH)
    diver = Diver(DATA_DIR, atlas=atlas)

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


# --- atlas ---


def atlas_cmd(args):
    atlas = Atlas(ATLAS_PATH)

    if args.atlas_cmd == "show":
        print(atlas.to_display(value_chain_id=getattr(args, "value_chain", None)))

    elif args.atlas_cmd == "init":
        existing_value_chains = {r.id for r in atlas.list_value_chains()}
        added_value_chains, added_companies, updated_companies = [], [], []

        for r in FRAMEWORK_VALUE_CHAINS:
            if r["id"] not in existing_value_chains:
                atlas.add_value_chain(r["id"], r["name"], r.get("description", ""))
                added_value_chains.append(r["name"])

            # Populate companies from seed data
            value_chain_obj = atlas.get_value_chain(r["id"])
            existing_tickers = {n.ticker for n in (value_chain_obj.companies if value_chain_obj else [])}
            for company in SEED_NODES.get(r["id"], []):
                if company["ticker"] not in existing_tickers:
                    try:
                        atlas.add_company(
                            value_chain_id=r["id"],
                            ticker=company["ticker"],
                            stage=company["stage"],
                            name=company.get("name", ""),
                            market=company.get("market", "US"),
                            role=company.get("role", ""),
                            source="seed",
                            peer_group=company.get("peer_group", ""),
                            causal_edge=company.get("causal_edge", ""),
                            behind_reason=company.get("behind_reason", ""),
                            competitor_tickers=company.get("competitor_tickers", []),
                            leader_tickers=company.get("leader_tickers", []),
                        )
                        added_companies.append(f"{company['ticker']} ({r['id']})")
                    except ValueError:
                        pass  # already exists
                else:
                    existing_company = next((n for n in value_chain_obj.companies if n.ticker == company["ticker"]), None)
                    metadata = {
                        "peer_group": company.get("peer_group", ""),
                        "causal_edge": company.get("causal_edge", ""),
                        "behind_reason": company.get("behind_reason", ""),
                        "competitor_tickers": company.get("competitor_tickers", []),
                        "leader_tickers": company.get("leader_tickers", []),
                    }
                    missing_metadata = {
                        key: value
                        for key, value in metadata.items()
                        if value and existing_company is not None and not getattr(existing_company, key, None)
                    }
                    if missing_metadata and atlas.update_company(r["id"], company["ticker"], **missing_metadata):
                        updated_companies.append(f"{company['ticker']} ({r['id']})")

        if added_value_chains:
            print(f"Added value_chains: {', '.join(added_value_chains)}")
        if added_companies:
            print(f"Added {len(added_companies)} companies from V1 ticker matrix")
        if updated_companies:
            print(f"Updated {len(updated_companies)} existing companies with peer metadata")
        if not added_value_chains and not added_companies and not updated_companies:
            print("Atlas already up to date.")
        print(atlas.to_display())

    elif args.atlas_cmd == "value_chain-add":
        try:
            atlas.add_value_chain(args.id, args.name, getattr(args, "description", "") or "")
            print(f"Added value_chain: [{args.id}] {args.name}")
        except ValueError as e:
            print(f"Error: {e}")

    elif args.atlas_cmd == "value_chain-remove":
        if atlas.remove_value_chain(args.id):
            print(f"Removed value_chain: {args.id}")
        else:
            print(f"Value Chain not found: {args.id}")

    elif args.atlas_cmd == "company-add":
        try:
            company = atlas.add_company(
                value_chain_id=args.value_chain,
                ticker=args.ticker,
                stage=args.stage,
                name=getattr(args, "name", "") or "",
                market=getattr(args, "market", "US") or "US",
                role=getattr(args, "role", "") or "",
                notes=getattr(args, "notes", "") or "",
                peer_group=getattr(args, "peer_group", "") or "",
                causal_edge=getattr(args, "causal_edge", "") or "",
                behind_reason=getattr(args, "behind_reason", "") or "",
                competitor_tickers=_csv_arg(getattr(args, "competitor_tickers", "")),
                leader_tickers=_csv_arg(getattr(args, "leader_tickers", "")),
            )
            print(f"Added company: {company.ticker} [{company.stage}] to value_chain '{args.value_chain}'")
        except ValueError as e:
            print(f"Error: {e}")

    elif args.atlas_cmd == "company-update":
        kwargs = {
            k: v for k, v in vars(args).items()
            if k in ("stage", "name", "market", "role", "notes", "peer_group", "causal_edge", "behind_reason")
            and v is not None
        }
        if getattr(args, "competitor_tickers", None) is not None:
            kwargs["competitor_tickers"] = _csv_arg(args.competitor_tickers)
        if getattr(args, "leader_tickers", None) is not None:
            kwargs["leader_tickers"] = _csv_arg(args.leader_tickers)
        if atlas.update_company(args.value_chain, args.ticker, **kwargs):
            print(f"Updated {args.ticker} in value_chain '{args.value_chain}'")
        else:
            print(f"Company not found: {args.ticker} in value_chain '{args.value_chain}'")

    elif args.atlas_cmd == "company-remove":
        if atlas.remove_company(args.value_chain, args.ticker):
            print(f"Removed {args.ticker} from value_chain '{args.value_chain}'")
        else:
            print(f"Company not found: {args.ticker} in value_chain '{args.value_chain}'")

    elif args.atlas_cmd == "news-add":
        atlas.add_news(
            ticker=args.ticker,
            title=args.title,
            url=args.url,
            source=args.source,
            date=getattr(args, "date", None),
        )
        print(f"Added news for {args.ticker}: {args.title[:60]}")

    else:
        print("Unknown atlas command.")
        print("Use: show, init, value_chain-add, value_chain-remove, company-add, company-update, company-remove, news-add")


# --- discover ---


def discover_cmd(args):
    atlas = Atlas(ATLAS_PATH)
    discoverer = Discoverer(DATA_DIR, TICKERS_FILE, atlas)

    if args.ticker:
        # Classify a specific ticker
        print(f"Classifying {args.ticker}...")
        result = discoverer.classify_ticker(args.ticker)
        _print_suggestion(result)
        if (
            result
            and args.auto
            and result.get("fits_existing_value_chain")
            and result.get("confidence") in ("high", "medium")
        ):
            _auto_add(atlas, result)

    elif args.keyword:
        # Keyword search → extract tickers → classify
        print(f"Searching for tickers related to: '{args.keyword}'...")
        results = discoverer.classify_keyword(args.keyword)
        for result in results:
            _print_suggestion(result)
            if args.auto and result.get("fits_existing_value_chain") and result.get("confidence") in ("high", "medium"):
                _auto_add(atlas, result)

    else:
        # Autonomous scan of BBS unknowns
        print("Scanning BBS hot tickers not yet in the atlas...")
        suggestions = discoverer.scan_unknown_tickers()
        if not suggestions:
            print("No high-confidence suggestions found.")
            return
        for result in suggestions:
            _print_suggestion(result)
            if args.auto and result.get("fits_existing_value_chain") and result.get("confidence") in ("high", "medium"):
                _auto_add(atlas, result)
            elif not args.auto:
                answer = input("Add to atlas? [y/n/skip] ").strip().lower()
                if answer == "y":
                    _auto_add(atlas, result)


def _print_suggestion(result: dict) -> None:
    if not result:
        print("(no classification returned)")
        return
    confidence = result.get("confidence", "?")
    fits = result.get("fits_existing_value_chain", False)
    print(f"\n[SUGGESTION — {confidence} confidence]")
    print(f"Ticker:  {result.get('ticker')} ({result.get('market', '?')})")
    if fits:
        print(f"Value Chain:   {result.get('value_chain_id')}")
        print(f"Stage:   {result.get('stage')}")
    else:
        new_value_chain = result.get("new_value_chain_name")
        print(
            f"Value Chain:   (new value_chain suggested: {new_value_chain})" if new_value_chain else "Value Chain:   (does not fit any known value_chain)"
        )
    print(f"Name:    {result.get('name', '')}")
    print(f"Role:    {result.get('role', '')}")
    print(f"Reason:  {result.get('reasoning', '')}")


def _auto_add(atlas: Atlas, result: dict) -> None:
    try:
        company = atlas.add_company(
            value_chain_id=result["value_chain_id"],
            ticker=result["ticker"],
            stage=result["stage"],
            name=result.get("name", ""),
            market=result.get("market", "US"),
            role=result.get("role", ""),
            source="discovery",
        )
        print(f"  -> Added {company.ticker} [{company.stage}] to value_chain '{result['value_chain_id']}'")
    except ValueError as e:
        print(f"  -> Could not add: {e}")


def _csv_arg(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().upper() for item in value.split(",") if item.strip()]


# --- decision ---


def decision_cmd(args):
    from elephant.decisions import is_suppressed, list_all, record, remove

    if args.decision_cmd == "record":
        entry = record(
            ticker=args.ticker,
            decision=args.decision,
            reason=args.reason or "",
            suppress_days=args.suppress_days,
            what_would_change=args.what_would_change or "",
        )
        print(f"Recorded: {entry['ticker']} → {entry['decision']}")
        if entry.get("suppress_until"):
            print(f"  Suppressed until: {entry['suppress_until']}")

    elif args.decision_cmd == "list":
        entries = list_all()
        if not entries:
            print("No decisions recorded.")
            return
        print(f"\n{'Ticker':<12} {'Decision':<16} {'Date':<12} {'Suppress Until':<14} Reason")
        print("-" * 80)
        for e in entries:
            sup = e.get("suppress_until") or ""
            marker = " [suppressed]" if is_suppressed(e["ticker"]) else ""
            print(f"{e['ticker']:<12} {e['decision']:<16} {e.get('date',''):<12} {sup:<14} {e.get('reason','')[:40]}{marker}")

    elif args.decision_cmd == "remove":
        if remove(args.ticker):
            print(f"Removed decision for {args.ticker}")
        else:
            print(f"No decision found for {args.ticker}")

    else:
        print("Unknown decision subcommand.")


# --- schedule ---


def sources_cmd(args):
    from elephant.source_adapters import ADAPTERS, get_adapters
    from elephant.source_registry import SourceRegistry, market_for_ticker
    from elephant.ticker_registry import normalize_ticker

    registry = SourceRegistry(SOURCE_REGISTRY_FILE)

    if args.sources_cmd == "check":
        if args.all:
            tickers = get_tickers(TICKERS_FILE, atlas_path=ATLAS_PATH)
        elif args.ticker:
            tickers = [normalize_ticker(args.ticker)]
        else:
            print("Use --ticker or --all.")
            return

        source_id = args.source
        if source_id and source_id not in ADAPTERS:
            print(f"Unknown source: {source_id}")
            print("Known sources: " + ", ".join(sorted(ADAPTERS)))
            return

        async def run_checks():
            count = 0
            for ticker in tickers:
                canonical = normalize_ticker(ticker)
                for adapter in get_adapters(source_id):
                    if market_for_ticker(canonical) not in adapter.supports_markets:
                        continue
                    availability = await adapter.check_availability(canonical)
                    registry.upsert_availability(availability)
                    registry.save()
                    count += 1
                    urls = ", ".join(availability.urls) if availability.urls else "-"
                    print(
                        f"{availability.ticker:<10} {availability.source_id:<18} "
                        f"{availability.status:<11} {urls}",
                        flush=True,
                    )
            return count

        count = asyncio.run(run_checks())
        print(f"Updated {SOURCE_REGISTRY_FILE}")
        print(f"Checked {count} ticker-source pairs")
        return

    if args.sources_cmd == "show":
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
        return

    print("Use: check, show")


def schedule_cmd(args):
    store = Store(DATA_DIR)

    bbs_rank_planner = BbsRankPlanner(store, TICKERS_FILE)
    yjp_planner = YahooFinancePlanner(store, TICKERS_FILE, atlas_path=ATLAS_PATH)
    minkabu_planner = MinkabuPlanner(store, TICKERS_FILE, atlas_path=ATLAS_PATH)
    news_planner = NewsPlanner(store)
    tdnet_planner = TDnetPlanner(store)
    price_planner = PricePlanner(store, TICKERS_FILE, atlas_path=ATLAS_PATH)
    source_availability_planner = SourceAvailabilityPlanner(store, TICKERS_FILE, atlas_path=ATLAS_PATH)

    multi_planner = MultiPlanner([
        bbs_rank_planner,
        yjp_planner,
        minkabu_planner,
        news_planner,
        tdnet_planner,
        price_planner,
        source_availability_planner,
    ])
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
                label = "Known-Ticker News"
            elif isinstance(task.harvester, TDnetHarvester):
                label = "TDnet Disclosures"
            elif isinstance(task.harvester, SourceAvailabilityHarvester):
                label = "Source Availability Check"
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

    sources_parser = subparsers.add_parser("sources", help="Check and inspect ticker source availability")
    sources_subs = sources_parser.add_subparsers(dest="sources_cmd")

    sources_check = sources_subs.add_parser("check", help="Check source availability for known tickers")
    sources_check.add_argument("--ticker", help="Canonical ticker to check")
    sources_check.add_argument("--all", action="store_true", help="Check all known tickers")
    sources_check.add_argument("--source", choices=["fool_quote_news", "minkabu", "yahoo_jp_bbs"], help="Limit to one source")

    sources_show = sources_subs.add_parser("show", help="Show source registry")
    sources_show.add_argument("--ticker", help="Canonical ticker to show")

    # atlas
    atlas_parser = subparsers.add_parser("atlas", help="Manage the atlas knowledge database")
    atlas_subs = atlas_parser.add_subparsers(dest="atlas_cmd")

    atlas_show = atlas_subs.add_parser("show", help="Display the atlas")
    atlas_show.add_argument("--value_chain", help="Show a specific value_chain by id")

    atlas_subs.add_parser("init", help="Seed the atlas with the 4 framework value_chains")

    value_chain_add = atlas_subs.add_parser("value_chain-add", help="Add a new value_chain")
    value_chain_add.add_argument("--id", required=True)
    value_chain_add.add_argument("--name", required=True)
    value_chain_add.add_argument("--description", default="")

    value_chain_rm = atlas_subs.add_parser("value_chain-remove", help="Remove a value_chain")
    value_chain_rm.add_argument("--id", required=True)

    company_add = atlas_subs.add_parser("company-add", help="Add a company to a value_chain")
    company_add.add_argument("--value_chain", required=True)
    company_add.add_argument("--ticker", required=True)
    company_add.add_argument("--stage", required=True, choices=["driver", "prime", "bottleneck", "capacity"])
    company_add.add_argument("--name", default="")
    company_add.add_argument("--market", default="US", choices=["US", "JP"])
    company_add.add_argument("--role", default="")
    company_add.add_argument("--notes", default="")
    company_add.add_argument("--peer-group", default="", dest="peer_group")
    company_add.add_argument("--causal-edge", default="", dest="causal_edge")
    company_add.add_argument("--behind-reason", default="", dest="behind_reason")
    company_add.add_argument("--competitor-tickers", default="", dest="competitor_tickers")
    company_add.add_argument("--leader-tickers", default="", dest="leader_tickers")

    company_upd = atlas_subs.add_parser("company-update", help="Update a company")
    company_upd.add_argument("--value_chain", required=True)
    company_upd.add_argument("--ticker", required=True)
    company_upd.add_argument("--stage", choices=["driver", "prime", "bottleneck", "capacity"])
    company_upd.add_argument("--name")
    company_upd.add_argument("--market", choices=["US", "JP"])
    company_upd.add_argument("--role")
    company_upd.add_argument("--notes")
    company_upd.add_argument("--peer-group", dest="peer_group")
    company_upd.add_argument("--causal-edge", dest="causal_edge")
    company_upd.add_argument("--behind-reason", dest="behind_reason")
    company_upd.add_argument("--competitor-tickers", dest="competitor_tickers")
    company_upd.add_argument("--leader-tickers", dest="leader_tickers")

    company_rm = atlas_subs.add_parser("company-remove", help="Remove a company")
    company_rm.add_argument("--value_chain", required=True)
    company_rm.add_argument("--ticker", required=True)

    news_add = atlas_subs.add_parser("news-add", help="Tag a news item to a ticker")
    news_add.add_argument("--ticker", required=True)
    news_add.add_argument("--title", required=True)
    news_add.add_argument("--url", required=True)
    news_add.add_argument("--source", required=True)
    news_add.add_argument("--date")

    # discover
    discover_parser = subparsers.add_parser("discover", help="Discover and classify tickers into the atlas")
    discover_parser.add_argument("--ticker", help="Classify a specific ticker")
    discover_parser.add_argument("--keyword", help="Search news for keyword and classify found tickers")
    discover_parser.add_argument("--auto", action="store_true", help="Auto-add high-confidence suggestions")

    dive_parser = subparsers.add_parser("dive", help="Deep dive research brief on a single ticker")
    dive_parser.add_argument("--ticker", required=True, help="Ticker to deep dive (e.g. 8105.T or NVDA)")

    tickers_parser = subparsers.add_parser("tickers", help="List tickers with harvested data in the last N days")
    tickers_parser.add_argument("--days", type=int, default=14, help="Lookback window in days (default: 14)")

    decision_parser = subparsers.add_parser("decision", help="Record or review pass/watch/value_chain_candidate decisions")
    decision_subs = decision_parser.add_subparsers(dest="decision_cmd")

    dec_record = decision_subs.add_parser("record", help="Record a decision for a ticker")
    dec_record.add_argument("--ticker", required=True)
    dec_record.add_argument("--decision", required=True, choices=["pass", "watch", "value_chain_candidate"])
    dec_record.add_argument("--reason", default="")
    dec_record.add_argument("--suppress-days", type=int, default=30, dest="suppress_days",
                            help="Days to suppress (for pass decisions, default 30)")
    dec_record.add_argument("--what-would-change", default="", dest="what_would_change")

    decision_subs.add_parser("list", help="List all recorded decisions")

    dec_rm = decision_subs.add_parser("remove", help="Remove a decision entry")
    dec_rm.add_argument("--ticker", required=True)

    args = parser.parse_args()

    if args.command == "fetch":
        asyncio.run(fetch_cmd(args))
    elif args.command == "query":
        query_cmd(args)
    elif args.command == "digest":
        digest_cmd(args)
    elif args.command == "schedule":
        schedule_cmd(args)
    elif args.command == "sources":
        sources_cmd(args)
    elif args.command == "atlas":
        atlas_cmd(args)
    elif args.command == "discover":
        discover_cmd(args)
    elif args.command == "dive":
        dive_cmd(args)
    elif args.command == "tickers":
        tickers_cmd(args)
    elif args.command == "decision":
        decision_cmd(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
