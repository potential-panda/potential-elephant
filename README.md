# Potential Elephant

A self-directed investment research scout built on the **Thematic Supply Chain Rotation Framework**. It monitors BBS sentiment, analyst consensus, and news signals across JP and US markets, maintains a structured map of investment opportunities ("the river tree"), and surfaces daily hints — stocks, sectors, and themes worth investigating that you probably haven't noticed yet.

The system opens doors. You walk through them or not.

---

## Concept: The River Framework

Major macro trends flow like rivers — capital moves from a source through upstream enablers, into middle-stream bottlenecks (the highest-alpha layer), and out through lower-stream capacity constraints.

```
Source (CapEx) → Upper Stream (core designers) → Middle Stream (bottlenecks ★) → Lower Stream (infrastructure)
```

The system maintains a **River Tree** — a structured map of instruments across 4 rivers:

| River | Theme |
|---|---|
| `ai_infra` | AI Infrastructure Supercycle |
| `tech_local` | Tech Localization & Onshoring |
| `physical_ai` | Embodied Physical AI |
| `longevity` | Demographic Longevity |

---

## How It Works

There are two data sources and one human-in-the-loop workflow that connects them.

### Data Source 1 — Yahoo BBS Pipeline (automated)

```
BBS Ranking → tickers.txt (LRU cache) → per-ticker scraping → Parquet storage
```

- **`yjp_bbs_rank`**: scrapes Yahoo Finance JP's daily BBS activity ranking and writes `tickers.txt` — an LRU cache (TTL=7 days, max=300 tickers). The backing `tickers.cache.json` records `last_seen`, `last_scraped_at`, and `speed_history` (comments per hour, one entry per scrape day) for each ticker.
- **`yahoo_comments` + `yahoo_evaluations`**: for every ticker in `tickers.txt`, scrapes BBS discussion posts and the bull/bear sentiment graph.
- **`minkabu_raw_html`**: scrapes Minkabu analyst consensus pages for the same tickers.
- **`news_headlines`**: 7 RSS feeds (NHK Business, Google News — JP economy, semiconductors, AI infra, robotics, biotech, power grid).

All scraped data is stored as Hive-partitioned Parquet under `$DATA_DIR`.

### Data Source 2 — River Tree (manual, human-curated)

```
You → tree node-add/update/remove → river_tree.json
```

The River Tree is a structured knowledge database of instruments you've already evaluated and decided to track. It is **never written automatically** — every entry reflects a deliberate decision. You add tickers after a deep dive confirms they belong.

### Workflow — Discovery → Deep Dive → Tree Update

```
digest (daily hints) ──┐
discover (scan BBS)  ──┼──► dive --ticker X ──► tree node-add  (or ignore)
discover --keyword   ──┘
```

1. **`digest`** runs two LLM calls daily: one on JP sources (BBS rankings + Minkabu, in Japanese) and one on EN sources (news + river tree gaps, in English). Produces 5–7 hints: `[NEW NAME]`, `[HOLDING SIGNAL]`, `[SECTOR THEME]`, `[RIVER GAP]`, `[MACRO OBSERVATION]`.
2. **`discover`** scans BBS hot tickers not yet in the tree, or searches news by keyword, and uses Claude to classify each ticker into a river and layer.
3. **`dive --ticker X`** produces a full research brief: company overview, BBS sentiment trend, Minkabu consensus, price context, news mentions, and a river fit verdict (`→ Add to watchlist | → River candidate | → Pass for now`).
4. You decide. If it belongs, `tree node-add` promotes it into the river.

---

## Setup

```bash
pip install playwright playwright-stealth duckdb pandas pyarrow anthropic feedparser schedule
pip install potential-panda-core  # internal dependency
playwright install chromium

export ANTHROPIC_API_KEY=sk-...
```

---

## Quick Start

```bash
# 1. Initialise the river tree with the V1 ticker universe (48 instruments)
python src/cli.py tree init

# 2. View the tree
python src/cli.py tree show

# 3. Fetch fresh signals (BBS ranking + news)
python src/cli.py fetch --dataset yjp_bbs_rank
python src/cli.py fetch --dataset news_headlines

# 4. Generate today's digest
python src/cli.py digest
```

---

## CLI Reference

### Data Collection

```bash
# Fetch data for testing (2 random tickers)
python src/cli.py fetch --dataset yahoo_comments
python src/cli.py fetch --dataset yahoo_evaluations
python src/cli.py fetch --dataset minkabu_raw_html
python src/cli.py fetch --dataset yjp_bbs_rank      # updates tickers.txt with hot stocks
python src/cli.py fetch --dataset news_headlines     # RSS: NHK, Reuters, Google News

# Run the long-running daily scheduler
python src/cli.py schedule
python src/cli.py schedule --dry-run    # preview the day's task plan
```

### Digest

```bash
python src/cli.py digest
```

Generates a Daily Digest using Claude — 5-8 hints of type:
- `[NEW NAME]` — a ticker not yet in the river tree with unusual BBS activity
- `[RIVER GAP]` — an empty or thin layer in a known river worth filling
- `[HOLDING SIGNAL]` — sentiment holding strong despite a price drop
- `[SECTOR THEME]` — multiple tickers pointing at the same theme
- `[MACRO OBSERVATION]` — a macro or currency angle worth watching

Saved to `$DATA_DIR/digests/YYYY-MM-DD.md`.

### River Tree

```bash
# View
python src/cli.py tree show
python src/cli.py tree show --river ai_infra

# Initialise with V1 ticker universe
python src/cli.py tree init

# Rivers
python src/cli.py tree river-add --id <id> --name <name> [--description <text>]
python src/cli.py tree river-remove --id <id>

# Nodes
python src/cli.py tree node-add --river <id> --ticker <ticker> --layer <layer> \
    [--name <name>] [--market US|JP] [--role <text>] [--notes <text>]
python src/cli.py tree node-update --river <id> --ticker <ticker> [--layer <layer>] \
    [--name <name>] [--role <text>] [--notes <text>]
python src/cli.py tree node-remove --river <id> --ticker <ticker>

# Tag news to a ticker
python src/cli.py tree news-add --ticker <ticker> --title <title> --url <url> --source <source>
```

Layers: `source` · `upper` · `middle` · `lower`

### Discovery

```bash
# Classify a specific ticker into the river tree
python src/cli.py discover --ticker 6146.T

# Search recent news by keyword, extract and classify tickers found
python src/cli.py discover --keyword "optical transceiver"

# Autonomous scan: BBS hot tickers not yet in the tree
python src/cli.py discover

# Any of the above with --auto to add high-confidence suggestions without prompting
python src/cli.py discover --auto
python src/cli.py discover --ticker NBIS --auto
```

### Deep Dive

```bash
# Full research brief on a single ticker
python src/cli.py dive --ticker 8105.T
python src/cli.py dive --ticker NVDA
```

Produces a structured brief with: company overview, BBS sentiment trend, Minkabu consensus,
price context (yfinance), news mentions, river fit assessment, and a verdict.
Saved to `$DATA_DIR/dives/YYYY-MM-DD-{ticker}.md` (and `.html` with clickable links).

### Query Stored Data

```bash
python src/cli.py query --dataset yahoo_comments --ticker 7203
python src/cli.py query --dataset yahoo_comments --ticker 7203 --start 2026-03-01 --end 2026-03-16
python src/cli.py query --dataset yahoo_evaluations --ticker 7203
python src/cli.py query --dataset minkabu_raw_html --ticker 7203
```

---

## Architecture

```
src/elephant/
  framework.py            # Store, Harvester, Planner, Scheduler base classes
  tickers.py              # Read/sample tickers.txt

  yjp/                    # Yahoo Finance JP BBS scraper
    harvester.py          #   comments + buy/sell evaluations per ticker
    planner.py            #   randomised daily schedule

  minkabu/                # Minkabu analyst consensus scraper
    harvester.py          #   analysis / research / pick / consensus pages (raw HTML)
    planner.py

  yjp_bbs_rank/           # Yahoo Finance BBS activity ranking
    harvester.py          #   scrapes hot tickers → writes tickers.txt
    planner.py

  news/                   # RSS news harvester
    harvester.py          #   NHK Business, Reuters, Google News (JP economy / semi / AI)
    planner.py            #   3x daily schedule

  tdnet/                  # TDnet timely disclosure harvester
    harvester.py          #   scrapes release.tdnet.info, filters to watched tickers
    planner.py            #   4x daily on market days (8, 12, 15, 18 JST)

  river/                  # River Tree — the knowledge database
    tree.py               #   RiverTree, River, Node, NewsItem + JSON persistence
    discoverer.py         #   Claude-powered ticker classification into rivers
    seed.py               #   V1 ticker universe (48 instruments, 4 rivers)

  synthesizer.py          # Reads all signals + river tree → calls Claude → digest
  diver.py                # Deep dive brief on a single ticker (price, BBS, Minkabu, news, river fit)
  ticker_registry.py      # Shared LRU cache: last_seen, last_scraped_at, speed_history per ticker
  query_interface.py      # Pandas helpers for external analysis

src/cli.py                # CLI entry point
```

### Data Storage

All data lives under `$DATA_DIR` (default: `/panda-infra/elephant`):

```
river_tree.json                                      # river tree knowledge database
tickers.txt                                          # active ticker list (LRU, plain text)
tickers.cache.json                                   # LRU cache: last_seen, speed_history per ticker
digests/YYYY-MM-DD.md                               # daily digests
dives/YYYY-MM-DD-{ticker}.md                        # deep dive briefs
dataset=yahoo_comments/ticker={t}/date={d}/         # BBS comments
dataset=yahoo_evaluations/ticker={t}/YEAR={y}/      # BBS buy/sell evaluation
dataset=minkabu_raw_html/ticker={t}/YEAR={y}/       # Minkabu analyst pages
dataset=news_headlines/date={d}/                    # RSS news headlines
```

All datasets are Parquet files, partitioned for fast date-range queries.

---

## Roadmap

| Step | Status | Description |
|---|---|---|
| BBS + Minkabu scraping | ✅ done | Daily sentiment pipeline |
| News RSS harvester | ✅ done | NHK, Reuters, Google News |
| Daily Digest (LLM) | ✅ done | Bilingual digest: JP hints (BBS/Minkabu) + EN hints (news/river gaps) |
| River Tree | ✅ done | Knowledge database with CRUD CLI |
| Discovery Engine | ✅ done | `discover` command, autonomous + targeted |
| Deep Dive | ✅ done | `dive --ticker X` — full research brief on demand |
| Price / volume data | ✅ done | Live yfinance fetch at digest time for top 40 tickers (1-month change) |
| Comment speed history | ✅ done | Comments/hour per ticker tracked in cache, fed into digest as velocity signal |
| TDnet integration | ✅ done | JP timely disclosures scraped 4×/day, filtered to watched tickers, included in digest |

---

## Docs

- `spec/SPEC.md` — system specification and design rationale
- `doc/river_framework.md` — Thematic Supply Chain Rotation Framework summary
- `doc/spec.md` — low-level BBS scraper selectors and schema
