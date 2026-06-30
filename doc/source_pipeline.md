# Source Pipeline

Potential Elephant should treat tickers, source availability, harvesting, and
analysis as separate stages. Today those concerns are partially mixed across
`tickers.txt`, `tickers-us.txt`, ticker cache flags, source-specific planners,
and harvesters. The target model below makes each component explicit.

Current boundary: the pipeline is centered on known tickers. General market
news, RSS feeds, and broad news pages can be useful later for finding new
tickers, but that is a separate future component and is disabled for now.

## Components

### 1. Ticker Registry

The ticker registry is the universe of instruments the system may care about.

Inputs:
- `tickers.txt`: active JP/BBS-ranked tickers and manually tracked JP tickers.
- `tickers-us.txt`: active US tickers known to have at least one supported source.
- River tree tickers: human-curated tracked companies.
- Optional watchlist/manual imports.

The registry should answer:
- What ticker symbols exist?
- Which market is each ticker in?
- Is this ticker active, watched, dormant, or ignored?
- Which canonical symbol should be used in datasets?
- Which source-specific ticker strings are known aliases, if any?

This is not the same as source availability. A ticker can exist even if no
scraper currently supports it.

Canonical ticker rule:
- The system should store one canonical ticker string for each instrument.
- For JP equities, use the Yahoo-style canonical form with exchange suffix, for
  example `7203.T`.
- For US equities, use the plain symbol, for example `SMCI`.
- Dataset partition paths, analysis records, score records, and UI routes should
  use the canonical ticker.
- Source-specific symbol variants such as `7203` vs `7203.T` are aliases, not
  canonical tickers.

### 2. Source Registry

The source registry is the ticker-to-source database. It records which source
URLs are currently valid for each ticker.

Recommended storage:

```json
{
  "SMCI": {
    "market": "US",
    "sources": {
      "fool_quote_news": {
        "status": "available",
        "urls": ["https://www.fool.com/quote/nasdaq/smci/"],
        "source_symbol": "smci",
        "last_discovered_at": "2026-06-30T12:00:00",
        "last_harvested_at": "2026-06-30T18:00:00",
        "last_error": null
      },
      "yahoo_jp_bbs": {
        "status": "unavailable",
        "urls": [],
        "source_symbol": "SMCI",
        "last_discovered_at": "2026-06-30T12:00:00",
        "last_harvested_at": null,
        "last_error": "no forum page"
      }
    }
  }
}
```

Statuses:
- `unknown`: not checked yet.
- `available`: source has at least one valid URL for this ticker.
- `unavailable`: source was checked and no valid URL exists.
- `degraded`: source exists, but recent harvests are failing.
- `retired`: source was deliberately disabled for this ticker.

This replaces source-specific cache flags such as `has_yahoo_jp_bbs` and
`has_minkabu_us` over time.

The source registry is also where source-specific URL resolution belongs. For
example:
- Canonical ticker `7203.T` may become source symbol `7203` for Minkabu.
- Canonical ticker `7203.T` may remain `7203.T` for Yahoo Finance JP.
- Canonical ticker `SMCI` may become lowercase `smci` in Fool quote URLs.

Once a URL is stored here, the harvester should not re-derive it from the
ticker.

### 3. Source Availability Check

Use `source availability check` as the general process name.

Reasoning:
- `discovery` sounds like finding brand-new sources, which is a different
  future component.
- `check` is clear at the CLI level: check whether a known source supports a
  known ticker.
- `probe` is acceptable as an implementation-level verb when a source check is
  lightweight or speculative.
- Individual implementations should expose `check_availability(ticker)`.

A source availability check job should:
- Iterate over tickers from the ticker registry.
- For each source adapter, build candidate URLs.
- Load lightweight pages or endpoints.
- Decide whether the ticker is supported.
- Save source-specific ticker strings, canonical source URLs, and availability
  status.

This stage intentionally consumes symbol-format gaps between sources. If a
source omits `.T`, lowercases US tickers, uses exchange path segments, or
requires any other URL-specific ticker form, the availability check handles it
and writes the exact URL into the source registry.

Run cadence:
- Full availability check: weekly across all tickers and all sources.
- Incremental availability check: daily for new tickers or sources with
  `unknown` status.
- Manual availability check: CLI command for a ticker/source during development.

### 4. Harvesters

A harvester fetches content from a source URL already confirmed by the source
registry.

Examples:
- Yahoo JP BBS harvester: comments and bull/bear evaluations.
- Minkabu harvester: analyst/research pages.
- Fool quote-news harvester: ticker-scoped Fool article metadata.
- TDnet harvester: market-wide disclosures, not ticker URL based.
- Price harvester: market data, not source-availability based.

Disabled for now:
- General RSS/news feeds and broad market news pages. These are better treated
  as future ticker/source discovery inputs, not daily known-ticker harvesters.

Harvester rules:
- Do not decide whether a ticker-source pair exists during normal harvesting.
- Do not transform canonical tickers into source-specific URL strings.
- Read the exact URL from the source registry and scrape it as-is.
- Record `last_harvested_at`, row counts, and errors back to the source registry.
- If repeated harvests fail, mark the ticker-source pair as `degraded`.
- Store raw/source-backed content in datasets with enough provenance to trace
  every later analysis point back to a URL.

### 5. Scheduler

The scheduler should plan work from the source registry.

Target behavior:
- Per-source harvesting is distributed across the day.
- Different sources can run in parallel.
- Tickers within one source are spread out to avoid bursts against one website.
- Availability checks and harvesting are separate task classes.
- Daily analysis starts only after the required daily harvest window is complete.

Suggested daily shape:

```text
01:00  rebuild plan
02:00  price harvest batch
07:00  JP/US source harvest wave 1
12:00  JP/US source harvest wave 2
18:00  JP/US source harvest wave 3
20:00  daily analysis
Sunday 03:00 full source availability check
```

Scheduling should use source metadata:
- `harvest_cadence`: hourly, daily, 3x daily, weekly.
- `max_parallel`: how many tasks for this source can run together.
- `min_spacing_minutes`: minimum delay between tasks for the same source.
- `market_window`: preferred market/time-zone window.
- `priority`: sources needed before daily analysis should finish first.

### 6. Daily Analysis

Daily analysis should be a separate stage after collection.

Inputs per ticker:
- Latest harvested content by source.
- Source registry availability and freshness.
- Price history.
- River tree context.
- Decision memory.

LLM jobs should produce structured intermediate facts, not the final score
directly:
- `summary`: concise source-backed ticker summary.
- `sentiment`: bullish, neutral, bearish, mixed, or unknown.
- `sentiment_confidence`: 0-1.
- `catalysts`: list of source-backed catalysts.
- `risks`: list of source-backed risks.
- `river_relevance`: fit to existing river/layer, if any.
- `evidence`: URL-backed references used by the analysis.

The final score should be calculated by deterministic code from structured
facts and numeric signals. The LLM can classify and summarize, but the final
number should come from a formula.

## Source Adapter Contract

Each source should have a small adapter with two responsibilities:

```python
class SourceAdapter:
    source_id: str
    supports_markets: set[str]
    harvest_cadence: str
    max_parallel: int
    min_spacing_minutes: int

    async def check_availability(self, ticker: str) -> SourceAvailability:
        ...

    def create_harvester_tasks(self, ticker: str, source_record: dict) -> list[HarvesterTask]:
        ...
```

`SourceAvailability` should include:
- `ticker`
- `source_id`
- `status`
- `source_symbol`
- `urls`
- `checked_at`
- `error`

This lets new sources follow one path:
1. Add a source adapter.
2. Implement `check_availability`.
3. Implement or connect a harvester.
4. Register the adapter.
5. Weekly availability checks and the daily scheduler pick it up automatically.

## Migration Plan

### Phase 1: Introduce Source Registry

Add a `source_registry.json` file beside `tickers.txt`.

Backfill it from current flags:
- `has_yahoo_jp_bbs` -> `yahoo_jp_bbs`
- `has_minkabu_us` -> `minkabu_us`
- JP tickers -> `minkabu_jp` and `yahoo_jp_bbs` as `unknown` or `available`
  depending on existing harvested data.
- Fool quote URLs -> `fool_quote_news` discovered for US tickers.

Keep `tickers-us.txt` during migration as a compatibility file.

### Phase 2: Move Availability Checks Out Of Harvesters

Current harvesters sometimes discover availability while scraping. Move that
logic into source availability-check adapters.

Planner behavior should change from:
- "include ticker unless source-specific cache flag says no"

to:
- "include ticker only when source registry says source is available and due"

### Phase 3: Build Source-Aware Scheduler

Replace source-specific planner assumptions with one planner that reads:
- ticker registry
- source registry
- source adapter metadata
- last harvest timestamps

The planner emits distributed tasks per source.

### Phase 4: Add Analysis Jobs

After daily harvest completion:
- Build one per-ticker evidence packet.
- Call LLM for structured analysis.
- Save `dataset=ticker_daily_analysis/ticker={ticker}/date={date}`.
- Compute deterministic final score.
- Feed candidates, digest, and UI from the same analysis records.

## Recommended Names

Use these names consistently:

| Concept | Recommended name | Avoid |
|---|---|---|
| Ticker universe | `TickerRegistry` | ticker cache |
| Ticker-source URL DB | `SourceRegistry` | source cache |
| Availability scan | `SourceAvailabilityCheck` | source discovery |
| One source implementation | `SourceAdapter` | scraper config |
| Content fetcher | `Harvester` | crawler |
| Daily post-harvest LLM pass | `DailyAnalysis` | digest generation |
| Per-ticker LLM input | `EvidencePacket` | prompt blob |
| Final numeric output | `ResearchScore` | LLM score |

The CLI names can be:

```bash
python src/cli.py sources check --ticker SMCI
python src/cli.py sources check --all
python src/cli.py sources show --ticker SMCI
python src/cli.py schedule --dry-run
python src/cli.py analyze --date 2026-06-30
```

Reserve `SourceDiscovery` for a future component that finds entirely new
websites, APIs, feeds, or source types that the system does not already know
about.

Reserve `TickerDiscovery` for a future component that scans general news,
market-wide articles, filings, screens, or social sources to suggest new
tickers for the ticker registry.
