# Value Chain Building and Maintenance System

Potential Elephant's atlas should be a living evidence database, not a
static watchlist. The goal is to use public theme pages, ETF holdings, existing
harvested news, and price relationships to propose atlas changes while keeping
human approval in control.

## Principles

- Store evidence separately from the curated atlas.
- Treat ETF holdings and public theme pages as external labels for
  ticker-theme membership.
- Use deterministic scores first. Use LLMs only to explain, classify ambiguous
  supply-chain stage, or propose a new value_chain name.
- Never silently promote a ticker into `atlas.json`. The system should
  generate `proposed` suggestions that a human accepts, rejects, or watches.
- Preserve the existing value_chain advantage: driver -> prime -> bottleneck -> capacity is
  about causal flow, not just keyword similarity.

## Data Sources

Primary sources to harvest or import are defined in one place:

- `src/elephant/theme/catalog.py`

That file contains:

- `THEME_DEFINITIONS`: value_chain/stage-aware theme identities
- `THEME_SOURCES`: source index links and extraction settings

To add a new source index page, add one
`ThemeSourceDefinition` entry to `THEME_SOURCES`. The builder should not need a
new hardcoded map for each source.

Supported source kinds:

- `theme_index`: first-stage page that links to many public themes or ETF
  baskets. The harvester stores raw themes in `theme_source_themes`, then
  crawls each detail page for tickers.
- `theme_page`: supported by the harvester, but not used in the active starting
  source list
- `etf_holdings`: supported for ad hoc local CSV imports, but not used in the
  active starting source list

Supported extractors:

- `html_theme_links`: extracts theme/detail links from a first-stage index page
- `html_ticker_regex`: extracts ticker codes from an HTML page
- `csv_holdings`: reads a holdings CSV using configured ticker/weight columns
- `html_holdings_regex`: extracts likely ticker symbols from an HTML holdings page

Active starting sources:

- `https://globalxetfs.co.jp/funds/list.html`
- `https://minkabu.jp/theme/popular_ranking`
- `https://kabutan.jp/info/accessranking/3_2`
- `https://www.stocktitan.net/stocks/themes`

These are all treated as first-stage `theme_index` pages. Each index produces
raw theme/detail links, then each detail page is harvested for tickers.
- Existing repo datasets:
  - `news_headlines`
  - `minkabu_raw_html`
  - `daily_prices`
  - `ticker_analysis_signals`
  - `atlas.json`

Useful public source catalogs and APIs:

- iShares ETF list: `https://www.ishares.com/us/products/etf-investments`
- Finnhub ETF holdings API: `https://finnhub.io/docs/api/etfs-holdings`
- API Ninjas ETF API: `https://api-ninjas.com/api/etf`
- Massive ETF constituents: `https://massive.com/docs/rest/partners/etf-global/constituents`
- Global X Japan thematic ETF example: `https://globalxetfs.co.jp/en/funds/2640/index.html`
- Kabutan trends: `https://en.kabutan.com/jp/trends`

## Dataset Model

The system uses these parquet datasets under `$ELEPHANT_DATA_DIR`:

- `dataset=theme_definitions`
  Theme IDs, names, value_chain mappings, stage hints, source URLs, and theme purity.
- `dataset=theme_source_themes`
  Raw first-stage themes discovered from each configured source, with source
  theme name, detail URL, rank, and deterministic canonical theme guess.
- `dataset=theme_members`
  Ticker membership from public theme pages such as Minkabu.
- `dataset=etf_holdings`
  ETF constituents with optional weights and a mapped theme ID.
- `dataset=ticker_theme_scores`
  Aggregated ticker-theme evidence scores.
- `dataset=value_chain_suggestions`
  Proposed value_chain-atlas companies with evidence and peer relationships.

The curated atlas remains `atlas.json`.

## Two-Stage Input Flow

The theme input side has two stages:

1. Source index -> raw themes
   - Example: `https://minkabu.jp/theme/popular_ranking`
   - Output: `theme_source_themes`
   - Fields: source ID, source theme name, source detail URL, rank, canonical
     theme guess.
2. Raw theme detail -> tickers
   - Example: a single Minkabu/Kabutan theme detail page
   - Output: `theme_members`
   - Fields: source theme ID, canonical theme ID if known, ticker, rank,
     source URL.

Raw themes whose names are not confidently consolidated are kept as `raw_*`
themes for audit, but they do not become final value_chain assignments.

## Theme Consolidation

The first version uses deterministic keyword consolidation in
`src/elephant/theme/catalog.py`:

- `THEME_DEFINITIONS`: canonical themes tied to value_chain/stage
- `THEME_KEYWORDS`: aliases and Japanese/English keywords used to map raw
  source theme names into canonical themes

Examples:

- `フィジカルAI` -> `physical_ai`
- `半導体` -> `ai_semiconductors`
- `半導体製造装置` -> `semiconductor_equipment`
- `データセンター` -> `ai_infrastructure`

LLM-assisted consolidation can be added later as a review pass over
`theme_source_themes` rows whose `canonical_theme_id` is empty.

## Scoring

For each `(ticker, theme)` pair:

```text
theme_score =
  ETF evidence
+ public theme page evidence
+ later: news/text evidence
+ later: price co-movement evidence
+ manual overrides
```

ETF evidence:

```text
etf_score =
  theme_purity
* issuer_quality
* recency_factor
* holding_factor
```

`holding_factor` is stronger when a ticker has a high ETF weight, but still
gives credit for membership when weight is missing.

Theme-page evidence:

```text
theme_page_score =
  source_quality
* theme_purity
* rank_factor
* source_weight
```

The final normalized relationship score is:

```text
normalized_score = 100 * (1 - exp(-raw_score / 2))
```

This rewards multiple independent confirmations but naturally saturates.

The system assigns a ticker to a canonical theme only when the relationship is
high. Assignment uses both an absolute score and a theme-relative rank, because
early source coverage can be sparse:

```text
assigned =
  normalized_score >= 50
  or evidence_count >= 2 and normalized_score >= 30
  or normalized_score >= max(28, theme_score_85th_percentile)
```

Rows below this threshold remain useful raw evidence, but they do not generate
value_chain suggestions.

## ETF Co-Membership and Grouping

The builder creates a ticker-theme evidence matrix:

```text
rows = tickers
columns = themes, ETFs, and source buckets
values = normalized evidence weights
```

Ticker similarity is cosine similarity over that matrix. This supports:

- peer group assignment
- same-row grouping in the value_chain view
- competitor ticker suggestions
- leader ticker suggestions

Example:

- ticker X appears in 10 AI ETFs
- ticker Y appears in 5 AI ETFs
- X should usually receive a stronger AI theme score
- if X and Y appear in the same ETFs with similar weights, they should be
  close peers in the value_chain view

## Value Chain Stage Classification

Theme membership alone should not choose a stage. Stage assignment should use
rules plus optional LLM review:

- `driver`: capital deployer, policy origin, demand creator
- `prime`: platform company, designer, OEM, primary enabler
- `bottleneck`: bottleneck component, materials, equipment, precision supplier
- `capacity`: infrastructure, logistics, power, real estate, deployment capacity

The current implementation uses `stage_hint` from the theme definition. Later
versions should add company description and LLM classification for ambiguous
cases.
## Maintenance Workflow

Weekly offline run:

1. Harvest starting source index pages and their theme detail pages.
2. Normalize tickers and source metadata.
3. Build ticker-theme scores.
4. Compute ticker similarity and peer candidates.
5. Compare suggestions with `atlas.json`.
6. Write `value_chain_suggestions`.
7. Apply maintenance in dry-run mode.
8. Review additions and removals in UI or CLI.
9. Apply accepted changes to the atlas.

Maintenance does two things:

- add high-score proposed companies
- remove low-score companies that were originally added by `source=theme_discovery`

Removal is intentionally conservative. It does not remove manual companies, and it
does not remove theme-discovered companies with a recorded human decision. If the
latest score dataset is missing, removal is skipped rather than treating every
company as zero score.

## Commands

List the configured source catalog:

```bash
PYTHONPATH=src python src/cli2.py themes sources
```

Harvest one configured source index or all enabled indexes:

```bash
PYTHONPATH=src python src/cli2.py themes harvest-sources --source kabutan_theme_ranking_3d
PYTHONPATH=src python src/cli2.py themes harvest-sources
```

Inspect raw first-stage themes:

```bash
PYTHONPATH=src python src/cli2.py themes source-themes --limit 50
```

Ad hoc CSV import remains available for experiments:

```bash
PYTHONPATH=src python src/cli2.py themes import-members --csv path/to/theme_members.csv
PYTHONPATH=src python src/cli2.py themes import-etf --csv path/to/etf_holdings.csv
```

Build scores and suggestions:

```bash
PYTHONPATH=src python src/cli2.py themes build --save
PYTHONPATH=src python src/cli2.py themes suggestions --limit 50
```

Preview and apply high-confidence suggestions:

```bash
PYTHONPATH=src python src/cli2.py themes apply --min-score 30 --dry-run
PYTHONPATH=src python src/cli2.py themes apply --min-score 30
```

By default, the same command also removes low-score theme-discovered companies whose
latest ticker-theme score is below `28`:

```bash
PYTHONPATH=src python src/cli2.py themes apply --min-score 30 --remove-min-score 28 --dry-run
PYTHONPATH=src python src/cli2.py themes apply --min-score 30 --remove-min-score 28
```

Skip removal for an add-only maintenance pass:

```bash
PYTHONPATH=src python src/cli2.py themes apply --keep-low-score
```

Apply one explicitly reviewed suggestion:

```bash
PYTHONPATH=src python src/cli2.py themes apply --suggestion-id <id>
```

Applied companies are added to `atlas.json` as `source=theme_discovery` and
`status=proposed`. They are not marked `active` until later review.

Expected CSV columns:

`theme_members`:

```text
theme_id,ticker,name,source,source_url,raw_rank,source_weight,theme_purity
```

`etf_holdings`:

```text
etf,theme_id,ticker,name,holding_weight,issuer,source_url,as_of,theme_purity,issuer_quality
```

Only `theme_id` and `ticker` are strictly required. Missing weights are handled
as capacity-confidence membership evidence.

## Starting sources

- https://globalxetfs.co.jp/funds/list.html (top 20)
- https://minkabu.jp/theme/popular_ranking (top 20)
- https://kabutan.jp/info/accessranking/3_2 (top 20)
- https://www.stocktitan.net/stocks/themes
