# Potential Elephant — System Specification

**Status:** Active Development
**Last updated:** 2026-05-23
**Note:** This spec iterates with usage. The real requirement only becomes clear once the output is running and the user sees what feels like a door vs. noise.

---

## 1. Purpose

Potential Elephant is a **research scout**. It monitors a broad set of financial signals across JP and US markets, then surfaces a short list of "doors" — areas, sectors, stocks, or ETFs worth the user's attention. The user investigates and decides. The system never trades.

**The goal is discovery, not prediction.**

The core problem it solves: **you can't search for something you don't know exists.** Without a signal pointing at NBIS or CLSK, you'd never type those tickers into a search box. The system's job is to be the person who already found the door and is telling you it's there.

This means **discovery breadth matters more than analytical depth.** A digest that surfaces 5 names the user has never heard of — with just enough context to decide if they're worth 30 minutes of research — is more valuable than a deep report on a stock they already follow.

### What it is not
- Not a trading bot
- Not a price prediction model
- Not a backtesting framework
- Not a portfolio manager

---

## 2. Target User Behavior

- **Holding period:** weeks to months
- **Research cadence:** check the digest daily or a few times per week
- **Flow:** read digest → pick 1-3 hints that resonate → use deep dive tool → do own research → decide
- **Markets:** JP stocks/ETFs, US stocks/ETFs

---

## 3. Two-Phase Design

### Phase 1 — Broad Observation → Hints (the Digest)

Cast a wide net across many signals. Surface a short list of hints — names, areas, or themes the user probably hasn't noticed. **Breadth over depth.** Each hint is 3-5 lines.

The user reads it in 5 minutes and decides what is worth following up.

### Phase 2 — Deep Dive (on demand)

The user picks one hint from the digest and asks for more. The system pulls all available depth signals for that specific ticker or theme and produces a focused research brief.

**Depth over breadth.** This is where TDnet PDFs, full BBS comment history, price charts, and news articles come in — but only for what the user is already interested in.

---

## 4. Phase 1: The Digest

### Output format

```
=== Elephant Digest · 2026-05-23 ===

[NEW NAME]
NBIS (Nebius Group): JP BBS discussion appeared this week, tone strongly bullish.
Not a JP stock — US-listed AI infrastructure company. You likely haven't seen this one.
→ Worth researching what they do before deciding if the sentiment makes sense.

[HOLDING SIGNAL]
4385.T (Mercari): price down 12% this week. BBS sentiment unchanged — strongest+strong still at 68%.
Analyst consensus on Minkabu holding at "buy". No negative signals found.
→ If you hold this, the thesis may still be intact. Worth revisiting before reacting to the dip.

[SECTOR THEME]
Semiconductor: BBS discussion volume up significantly on 3 mid-cap JP names this week.
Minkabu consensus shifted bullish on two of them in the past 48h.
→ Something may be building in this space. Worth a look at the sector before individual names.

[MACRO OBSERVATION]
Yen weakened to 158 this week. JP exporters historically benefit.
→ Auto and electronics sector ETFs may be worth watching.
```

### Hint types
- **New name:** a ticker or area the user is unlikely to know, surfaced by unusual BBS/sentiment activity
- **Holding signal:** price dropped but sentiment held — worth revisiting the thesis before reacting
- **Sector theme:** multiple signals pointing at the same industry or macro trend
- **Macro observation:** currency, rates, or geopolitical shift that opens a sector angle

### Principles
- **Short.** 5-8 hints maximum. Quality over coverage.
- **Source-cited.** Every hint states which signal triggered it.
- **Opinionated but humble.** "Worth looking at" not "Buy this."
- **Novel first.** Prioritize names the user does not already follow. Known names only appear if the signal is unusual (e.g. holding signal during a dip).
- **JP BBS covers US stocks too.** JP retail community discusses US names (AMD, NVDA, etc.) — treat these as valid discovery signals, not noise.

### Input signals for Phase 1

| Signal | Source | Status |
|---|---|---|
| BBS hot tickers (volume ranking) | Yahoo Finance JP BBS rank | ✅ built |
| BBS sentiment shifts per ticker | Yahoo Finance JP BBS evaluations | ✅ built |
| Analyst consensus changes | Minkabu (consensus, analysis pages) | ✅ built |
| Macro / news headlines | RSS: Nikkei, Reuters JP, NHK Business | ❌ not built |

The first three signals are already collected. The digest can be built and validated with those before adding news.

---

## 5. Phase 2: Deep Dive

### Trigger
User picks a hint: `python src/cli.py dive --ticker NBIS` or `python src/cli.py dive --theme "semiconductor"`

### Output
A focused research brief covering:
- **What they do:** one paragraph company/theme summary (LLM-generated)
- **BBS detail:** recent comment samples, sentiment trend over past 2 weeks
- **Analyst view:** full Minkabu analysis and consensus details
- **Disclosures:** recent TDnet releases (if JP) or SEC filings summary (if US)
- **Price context:** 52-week range, recent volume vs average, proximity to key levels
- **News:** recent headlines clustered by relevance

### Input signals for Phase 2

| Signal | Source | Status |
|---|---|---|
| BBS comments (full text) | Yahoo Finance JP BBS | ✅ built |
| Minkabu full pages | Minkabu (analysis, research, pick, consensus) | ✅ built |
| Timely disclosures | TDnet | 🔶 started (`src/ingestion/tdnet.py`) |
| Price + volume | yfinance (JP + US) | ❌ not built |
| News articles | RSS + web fetch | ❌ not built |

---

## 6. Development Plan

### Step 1 — Build the Digest (Phase 1 output)
- Build a `Synthesizer` that reads the last 48h of stored BBS + Minkabu data
- Call Claude API to produce the digest markdown
- Add `python src/cli.py digest` command
- Run it, read it, adjust the prompt until the output feels right

### Step 2 — Add News to the Digest
- Add RSS harvester: Nikkei, Reuters JP, NHK Business headlines
- Feed into `Synthesizer` to enrich macro and sector hints

### Step 3 — Build the Deep Dive (Phase 2 output)
- Add `python src/cli.py dive --ticker X` command
- Integrate TDnet (port `src/ingestion/tdnet.py` into elephant framework)
- Add yfinance harvester for price context
- LLM produces a focused research brief for the requested ticker/theme

### Step 4 — Tuning
- Annotate past digests ("useful", "already knew", "too noisy")
- Tune synthesis prompt based on what feels like a real door vs. noise

---

## 7. Data Storage

```
/panda-infra/elephant/
  dataset=yahoo_comments/ticker={ticker}/date={date}/data.parquet
  dataset=yahoo_evaluations/ticker={ticker}/YEAR={year}/data.parquet
  dataset=minkabu_raw_html/ticker={ticker}/YEAR={year}/data.parquet
  dataset=tdnet_disclosures/date={date}/data.parquet          # Step 3
  dataset=price_daily/ticker={ticker}/YEAR={year}/data.parquet # Step 3
  dataset=news_headlines/date={date}/data.parquet              # Step 2
  digests/YYYY-MM-DD.md                                        # Step 1
```

---

## 8. Low-Level Scraping Reference

Implementation details for the Yahoo Finance BBS scraper (selectors, schema, anti-detection) are documented in [`doc/spec.md`](../doc/spec.md).
