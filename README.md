# Potential Elephant

A self-directed investment **research triage system** built on a Thematic Supply Chain Rotation Framework.

It maintains a living map of thematic investment themes ("the river tree"), scores companies on research-worthiness using source-backed evidence, and surfaces a daily shortlist of names worth looking into today — without ever telling you to buy or sell anything.

The system opens doors. You walk through them or not.

---

## Core Concept

Major macro trends flow like rivers — capital moves from a source through upstream enablers into middle-stream bottlenecks (highest alpha), then out through lower-stream capacity constraints.

```
Source (CapEx) → Upper Stream (core enablers) → Middle Stream (bottlenecks ★) → Lower Stream (infrastructure)
```

Four rivers are tracked:

| River | Theme |
|---|---|
| `ai_infra` | AI Infrastructure Supercycle |
| `tech_local` | Tech Localization & Onshoring |
| `physical_ai` | Embodied Physical AI |
| `longevity` | Demographic Longevity |

The **River Tree** is the human-curated knowledge base at the center of everything. Every node reflects a deliberate decision: this company has a specific supply-chain role in this theme.

---

## Dashboard

The dashboard runs at `http://localhost:9765` (or wherever `elephant-api` is bound).

It has five primary views described below.

---

## The Candidates Page

**Daily use. Open this first.**

The Candidates page scores every tracked ticker on *research-worthiness* — not investment merit. A high score means "this name deserves 30 minutes of your attention today", not "buy this".

### Queues

Candidates are split into three queues:

| Queue | Label | Meaning |
|---|---|---|
| **A** | River Candidates | Deserves research today. Has real source-backed evidence, fits a confirmed river, and scores ≥ 70. |
| **B** | Known Node / Monitor | Approved or watched nodes with new disclosures, peer-relative divergence, or stale thesis risk. Score ≥ 40. |
| **C** | Crowd Heat / Noise | Active BBS attention but no confirmed river fit or source-backed catalyst. Do not prioritize. |
| Suppressed | — | Recently passed names hidden until suppression expires or a qualifying new catalyst appears. |

**Queue A is the only queue that requires your attention daily.** Queue B is a weekly monitor. Queue C is background awareness — it explains why a name is hot without recommending you act.

### Score Columns

| Column | What it means |
|---|---|
| Score | Final research-worthiness score 0–100 |
| River/Layer | Which river and supply-chain layer this ticker belongs to |
| Lag 1y | How far this ticker lags behind its same-layer peers (1-year return). Negative = lagging peers. |
| 1m / 3m / 1y | Price returns over 1 month, 3 months, 1 year |
| Bull% | Yahoo BBS bull sentiment percentage |
| BBS | Yahoo BBS rank today (● = seen today) |
| Catalyst | TD = TDnet disclosure in last 48h · MK = Minkabu data available |

### Expanded Row — Score Breakdown

Click any row to expand it. You'll see:

**Score Breakdown (D1–D6):**

| Dimension | Max | What it measures |
|---|---|---|
| D1 river fit | 25 | How strongly this ticker belongs to a confirmed river. 25 = active/weak node in primary river. 0 = no river connection. |
| D2 layer alpha | 15 | Layer momentum — peers moving up (+8), thin layer (+5), sparse coverage (+2). |
| D3 relative laggard | 20 | How far this ticker lags same-layer peers on 4-week and 12-week returns. Lagging = potential catch-up. |
| D4 catalyst | 20 | Quality and freshness of source-backed evidence: TDnet disclosures, policy events, company IR. Decays over 14 days. |
| D5 attention change | 10 | New attention signals: BBS rank improving, comment velocity up >20%, new Minkabu/analyst coverage. |
| D6 coverage gap | 10 | Research coverage gap — no analyst coverage scores higher than crowded coverage. Only counts if D1 > 0. |

**Adjustments shown below the breakdown:**
- `memory adj` — penalty for previously passed names (−10, −20, or −25 depending on pass count)
- `noise` — noise penalty (most negative single penalty wins, they don't stack):
  - BBS top 20 with no catalyst: −15
  - BBS top 10 + falling price: −20
  - Prior pump-and-retreat pattern: −10
  - Generic theme tag only: −8

**Evidence Packet** — every source item that contributed to the score, with:
- Role: `CATALYST` (company disclosure), `EVIDENCE` (river-supporting), `CONTEXT`, `ATTENTION` (BBS), `RISK`
- Source tier (1 = regulatory/government, 2 = TDnet/company primary, 3 = trade press, 4 = financial press, 5–6 = commentary/BBS)
- Freshness in days
- Points contributed

**Flags:**
- `weak_peer_set` — D3 = 0 because fewer than 3 active/weak peers have price history
- `Blocked:` — why a name didn't qualify for a higher queue
- `Suppressed until` — when suppression expires and pass count

### Decision Actions

Expand a row to record your decision. All decisions are appended (not overwritten) and persist decision memory across sessions.

| Button | Decision | Effect |
|---|---|---|
| **Pass** | `pass` | Suppresses this ticker for 28 days (1st pass), 42 days (2nd), or 84 days (3rd+). Score gets a memory penalty. |
| **Watch** | `watch` | Marks as being monitored. No suppression. |
| **River Candidate** | `river_candidate` | Flags for potential tree promotion. Appears in Watchlist. |
| **Research** | `needs_manual_research` | Marks for manual deep-dive within 7 days. |

Suppression resets early if a qualifying new catalyst appears — the threshold scales up with pass count (requires progressively stronger evidence from higher-tier sources).

You can optionally type a reason before clicking. The **Show suppressed** button reveals suppressed names for audit.

---

## Node Lifecycle

Nodes in the tree have six lifecycle states:

| Status | Meaning |
|---|---|
| `proposed` | Source-backed candidate, not yet approved |
| `active` | Fully accepted, currently monitored |
| `weak` | Relevant but evidence is thin or stale |
| `watch` | Interesting, waiting for stronger evidence |
| `dormant` | Structurally relevant but quiet — excluded from active layer counts and daily queues |
| `rejected` | Reviewed and not a fit; kept for institutional memory |

Only `active` and `weak` nodes count toward layer totals for D2 and D3 scoring. Dormant nodes are invisible to daily scoring but preserved in the tree.

---

## What This System Does Not Do

- No buy, sell, hold, or price target recommendations
- No portfolio construction advice
- No automated trading actions
- No fully automated node promotion (every tree change requires a human decision)
- No LLM-generated score facts — every score point traces back to a specific source

---

## Data Sources

| Source | Role in scoring |
|---|---|
| **TDnet** (timely disclosures) | D4 catalyst — highest weight (Tier 2, 1.0×). Fresh company-primary disclosures. |
| **Yahoo BBS ranking + comments** | D5 attention change only. Never D1 or D4. BBS-only names are blocked from Queue A. |
| **Minkabu** | D5 attention (new coverage), D6 coverage gap context, D2 "not crowded" signal |
| **Price/volume** (yfinance) | D3 relative laggard gap. Not a discovery or catalyst source. |
| **River Tree** | D1 river fit (primary signal), D2 peer set |

Source tiers: 1 (regulatory/government) · 2 (company primary/TDnet) · 3 (specialist trade press) · 4 (general financial press) · 5–6 (commentary/BBS, zero weight in D4)

---

## Setup

```bash
pip install playwright playwright-stealth duckdb pandas pyarrow anthropic feedparser schedule
pip install potential-panda-core
playwright install chromium

export ANTHROPIC_API_KEY=sk-...
export ELEPHANT_DATA_DIR=/path/to/data   # default: /panda-infra/elephant
```

Start the dashboard (also available as a systemd user service — see `elephant-api.service`):

```bash
python src/api.py
```

---

## CLI Reference

### Daily Data Collection

```bash
python src/cli.py fetch --dataset yjp_bbs_rank       # BBS hot tickers → tickers.txt
python src/cli.py fetch --dataset news_headlines      # Known-ticker news sources (general RSS disabled)
python src/cli.py fetch --dataset yahoo_evaluations   # BBS bull/bear sentiment
python src/cli.py fetch --dataset minkabu_raw_html    # Minkabu analyst pages
python src/cli.py schedule                            # run the daily scheduler
python src/cli.py schedule --dry-run                  # preview task plan
```

### Source Availability

Known ticker sources are tracked in `source_registry.json`. Availability checks
resolve exact source URLs, including source-specific ticker formats such as
`7203.T` vs `7203`.

```bash
python src/cli.py sources check --ticker SMCI --source fool_quote_news
python src/cli.py sources check --all
python src/cli.py sources show --ticker SMCI
```

### River Tree

```bash
python src/cli.py tree show
python src/cli.py tree show --river ai_infra

# Add a node after completing a deep dive
python src/cli.py tree node-add --river ai_infra --ticker 6146.T --layer middle \
    --name "Disco Corp" --market JP --role "Chemical-mechanical planarization equipment"

python src/cli.py tree node-update --river ai_infra --ticker 6146.T \
    --status active --notes "confirmed semiconductor exposure"
python src/cli.py tree node-remove --river ai_infra --ticker 6146.T
```

Layers: `source` · `upper` · `middle` · `lower`

Node statuses: `proposed` · `active` · `weak` · `watch` · `dormant` · `rejected`

### Research Tools

```bash
# Full research brief on a single ticker
python src/cli.py dive --ticker 6146.T

# Classify a ticker or keyword into the river tree
python src/cli.py discover --ticker 6146.T
python src/cli.py discover --keyword "optical transceiver"
python src/cli.py discover              # autonomous BBS scan

# Generate today's digest (LLM)
python src/cli.py digest
```

---

## Architecture

```
src/elephant/
  candidates.py           # D1–D6 scoring, queue assignment, evidence packet builder
  scoring.py              # Score functions for each dimension (stateless, testable)
  scoring_config.py       # Calibration constants (thresholds, keywords, tier weights)
  decisions.py            # Decision log — pass/watch/river_candidate/needs_manual_research
  maintenance.py          # Queue D generation from tree state + resolution log

  river/
    tree.py               # RiverTree, River, Node (lifecycle v2), JSON persistence
    discoverer.py         # Claude-powered ticker classification

  api/
    candidates.py         # GET /api/candidates
    tree.py               # GET /api/tree (with lifecycle metadata)
    maintenance.py        # GET /api/maintenance + POST /api/maintenance/{id}/resolve

  yjp_bbs_rank/           # Yahoo BBS rank scraper (28-day cache with daily rank)
  yjp/                    # Yahoo BBS comments + sentiment
  minkabu/                # Minkabu analyst consensus scraper
  tdnet/                  # TDnet timely disclosure scraper
  news/                   # RSS news harvester

src/api.py                # FastAPI server
src/cli.py                # CLI entry point
web/src/
  components/
    Candidates.jsx        # Daily triage — score breakdown, evidence, decision actions
    Tree.jsx              # River tree viewer with lifecycle status
    Watchlist.jsx         # river_candidate watchlist with since-flag returns
```

### Data Storage

All data under `$ELEPHANT_DATA_DIR` (default `/panda-infra/elephant`):

```
river_tree.json                          # river tree (v2, with lifecycle fields)
decisions.json                           # decision log (keyed by ticker)
tickers.txt                              # active BBS ticker list
tickers.cache.json                       # BBS cache: last_seen, speed_history (28-day rank)
digests/YYYY-MM-DD.md                    # daily LLM digests
dives/YYYY-MM-DD-{ticker}.md             # deep dive briefs
dataset=tdnet_disclosures/date={d}/      # TDnet disclosures
dataset=yahoo_evaluations/ticker={t}/    # BBS bull/bear sentiment
dataset=minkabu_raw_html/ticker={t}/     # Minkabu pages
dataset=news_headlines/date={d}/         # RSS headlines
dataset=daily_prices/ticker={t}/         # price history (yfinance)
```

---

## Docs

- `doc/river_framework.md` — Thematic Supply Chain Rotation Framework
- `STRATEGY.md` — the betting philosophy behind the framework
- `spec/SPEC.md` — system design rationale
