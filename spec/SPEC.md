# Potential Elephant — System Specification

**Status:** Active Development
**Last updated:** 2026-05-28
**Note:** This spec iterates with usage. The real requirement only becomes clear once the output is running and the user sees what feels like a door vs. noise.

---

## 1. Purpose

Potential Elephant is a **research scout** built around the Thematic Supply Chain Rotation Framework (see `doc/river_framework.md`). It maps financial instruments onto thematic "rivers" — structured supply chains flowing from capital sources through upstream enablers, middle-stream bottlenecks, and lower-stream capacity constraints.

The system surfaces investment opportunities the user hasn't noticed yet. The user investigates and decides. The system never trades.

**The core problem:** you can't search for something you don't know exists. The system finds the doors.

---

## 2. The River Framework

Each thematic river has four layers:

| Layer | Description | Alpha profile |
|---|---|---|
| **source** | Where CapEx or policy funding originates (e.g., hyperscaler balance sheets) | Low — large caps, well-covered |
| **upper** | Core designers absorbing the initial capital surge (e.g., GPU designers) | Medium |
| **middle** | Specialized suppliers where physical bottlenecks emerge (SSDs, HBM, optical transceivers, precision gears) | **Highest — 2-3x potential** |
| **lower** | Real-world capacity constraints sustaining the trend (power grids, utilities, logistics) | Medium — longer lag |

Known rivers (expandable):
1. **ai_infra** — AI Infrastructure Supercycle
2. **tech_local** — Tech Localization & Onshoring
3. **physical_ai** — Embodied Physical AI
4. **longevity** — Demographic Longevity

---

## 3. Two-Phase Design

### Phase 1 — River Tree Discovery & Maintenance

Two components working together to build and maintain a structured map of river instruments.

**Component 1: River Tree** (knowledge database)
- Stores rivers, nodes (instruments), and news linked to nodes
- Exposes `add_node()`, `add_news()`, `update_node()`, `remove_node()`, `find_ticker()`
- Persisted as a human-editable JSON file
- The source of truth for "what do we know"

**Component 2: Discovery Engine** (populates the tree)
- Scans BBS/news signals for tickers not yet in the tree
- Accepts a `--ticker` or `--keyword` input for targeted classification
- Calls Claude to classify: which river? which layer? what role?
- Proposes additions — user confirms, or `--auto` for high-confidence cases
- Also drives the Daily Digest: surfaces gaps in the tree and new candidates

### Phase 2 — Deep Dive (on demand)

User picks a node from the tree → system generates a full research brief:
full BBS comment history, TDnet disclosures, price context, news articles.

---

## 4. Component 1: River Tree

### Storage

JSON file at `$DATA_DIR/river_tree.json`. Human-editable and version-controllable.

```json
{
  "version": 1,
  "rivers": [
    {
      "id": "ai_infra",
      "name": "AI Infrastructure Supercycle",
      "description": "Hyperscaler CapEx → compute/storage bottlenecks → power infrastructure",
      "nodes": [
        {
          "ticker": "NVDA",
          "name": "NVIDIA",
          "market": "US",
          "layer": "upper",
          "role": "GPU designer and AI compute platform",
          "notes": "",
          "added": "2026-05-28",
          "source": "manual"
        },
        {
          "ticker": "NBIS",
          "name": "Nebius Group",
          "market": "US",
          "layer": "middle",
          "role": "AI cloud infrastructure provider",
          "notes": "Discovered via Yahoo JP BBS, strong bullish sentiment",
          "added": "2026-05-28",
          "source": "discovery"
        }
      ]
    }
  ],
  "news": {
    "NBIS": [
      {"title": "...", "url": "...", "source": "reuters", "date": "2026-05-28"}
    ]
  }
}
```

### API

```python
tree = RiverTree(path)

# Rivers
tree.add_river(id, name, description)
tree.remove_river(river_id)
tree.get_river(river_id) -> River
tree.list_rivers() -> list[River]

# Nodes
tree.add_node(river_id, ticker, layer, name, market, role, notes, source)
tree.update_node(river_id, ticker, **kwargs)
tree.remove_node(river_id, ticker)
tree.find_ticker(ticker) -> list[(River, Node)]

# News
tree.add_news(ticker, title, url, source, date)
tree.get_news(ticker) -> list[NewsItem]
```

### CLI

```bash
python src/cli.py tree show [--river <id>]        # display the full tree or one river
python src/cli.py tree init                        # seed with 4 river stubs from framework

python src/cli.py tree river-add --id <id> --name <name> [--description <desc>]
python src/cli.py tree river-remove --id <id>

python src/cli.py tree node-add --river <id> --ticker <ticker> --layer <layer> \
    [--name <name>] [--market US|JP] [--role <role>] [--notes <notes>]
python src/cli.py tree node-update --river <id> --ticker <ticker> \
    [--layer <layer>] [--name <name>] [--role <role>] [--notes <notes>]
python src/cli.py tree node-remove --river <id> --ticker <ticker>

python src/cli.py tree news-add --ticker <ticker> --title <title> --url <url> --source <source>
```

---

## 5. Component 2: Discovery Engine

### Autonomous scan

```bash
python src/cli.py discover [--auto]
```

1. Load BBS hot tickers (from `tickers.txt`)
2. Filter out tickers already in the tree
3. For each unknown ticker: load BBS evaluation + Minkabu + recent news
4. Call Claude: "Does this fit any known river? Which layer? What role?"
5. Print suggestions with confidence level
6. If `--auto`: add high-confidence suggestions directly to the tree

### Targeted classification

```bash
python src/cli.py discover --ticker NBIS [--auto]
python src/cli.py discover --keyword "optical transceiver" [--auto]
```

- `--ticker`: classify a specific ticker, show river/layer/role suggestion
- `--keyword`: scan news headlines for the keyword, extract mentioned tickers, classify each

### Output format

```
[SUGGESTION — high confidence]
Ticker: 6966.T (Mitsubishi Electric)
River:  ai_infra
Layer:  middle
Role:   Power electronics and transformer manufacturer for data center cooling
Reason: BBS discussion volume up 3x this week. News cluster around JP data center
        power supply constraints. Fits the physical bottleneck pattern for AI infra.

→ Add to tree? [y/n/skip]
```

### River-aware Digest

The `digest` command now uses the tree as context:
- Shows what layers are already populated per river
- Surfaces signals for existing nodes (sentiment shifts, news)
- Suggests candidates for empty or thin layers
- Flags new rivers forming that don't match existing ones

---

## 6. Input Signals

| Signal | Source | Cadence | Status |
|---|---|---|---|
| BBS hot tickers | Yahoo Finance JP BBS rank | Daily | ✅ built |
| BBS sentiment per ticker | Yahoo Finance JP BBS evaluations | Daily | ✅ built |
| Analyst consensus | Minkabu | Daily | ✅ built |
| News headlines | RSS (NHK, Reuters, Google News) | 3x daily | ✅ built |
| River tree (current knowledge) | `river_tree.json` | On demand | 🔶 building |
| Timely disclosures | TDnet | Daily | ❌ Step 3 |
| Price + volume | yfinance | Daily | ❌ Step 3 |

---

## 7. Development Plan

### Step 1 — River Tree (complete the knowledge database)
- `river/tree.py`: RiverTree, River, Node, NewsItem dataclasses + JSON persistence
- `river/discoverer.py`: Claude-powered ticker classification
- CLI: `tree show/init/river-add/river-remove/node-add/node-update/node-remove/news-add`
- CLI: `discover [--ticker X] [--keyword X] [--auto]`
- Update `synthesizer.py` to include tree context in the digest

### Step 2 — Deep Dive
- `python src/cli.py dive --ticker X` or `--river X`
- Pulls full depth signals for the requested node/river
- LLM generates a focused research brief

### Step 3 — Catalyst & Price Data
- TDnet integration (port `src/ingestion/tdnet.py`)
- yfinance harvester: daily OHLCV, 52-week range, volume anomalies
- Feed into both digest and deep dive

### Step 4 — Tuning
- Annotate past digests ("useful", "already knew", "noise")
- Tune synthesis prompt

---

## 8. Data Storage

```
$DATA_DIR (default: /panda-infra/elephant)
  river_tree.json                                      # Step 1
  digests/YYYY-MM-DD.md                               # built
  dataset=yahoo_comments/ticker={t}/date={d}/         # built
  dataset=yahoo_evaluations/ticker={t}/YEAR={y}/      # built
  dataset=minkabu_raw_html/ticker={t}/YEAR={y}/       # built
  dataset=news_headlines/date={d}/                    # built
  dataset=tdnet_disclosures/date={d}/                 # Step 3
  dataset=price_daily/ticker={t}/YEAR={y}/            # Step 3
```

---

## 9. Low-Level Scraping Reference

Yahoo Finance BBS scraper selectors and schema: [`doc/spec.md`](../doc/spec.md).
River framework source document: [`doc/river_framework.md`](../doc/river_framework.md).
