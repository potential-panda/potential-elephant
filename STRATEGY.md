# Investment Strategy

## Core Philosophy

This is a **betting framework**, not a traditional analysis framework.

Traditional technical/fundamental analysis explains what already happened — useful for
building pattern recognition over time, but not reliable for predicting the future.
Instead, the approach here is:

- Make many small bets across different thematic ideas
- Size each bet small enough to hold through being wrong
- Let the few that are correct pay off the others

Risk is managed through **position sizing and diversification**, not through trying to
predict with higher accuracy.

---

## The Thematic Wave Bet

**The core pattern:**

1. A thematic wave is confirmed by leader stocks already moving (2x–3x)
2. There exist structurally similar companies that *should* be in the wave
3. Those companies haven't been re-rated by the market yet — price is still "normal"
4. You buy before the catalyst, hold through noise, wait for the market to catch up

**The bet is not:** "this stock will go up"
**The bet is:** "the market hasn't priced this company into the theme yet, and eventually it will"

---

## Real Examples

### AMD (~$155 → ~$465, ~3x)
- Wave confirmed: NVDA, AVGO already demonstrated AI chip demand was real
- AMD is structurally equivalent (x86 CPU + GPU, solid enterprise customer base)
- Price had not moved — market hadn't connected AMD to AI infra yet
- Bet: a major AI company will eventually sign with AMD
- Catalyst: OpenAI chip partnership announced → re-rating happened

### CLSK (~$20, went to ~$8 before recovering)
- Wave confirmed: several crypto miners pivoted GPU infra to AI computing and got 2x–3x
- CLSK hadn't announced pivot yet, price followed crypto weakness downward
- Bet: CLSK will follow peers and pivot to AI computing
- Price dropped further after entry (wrong on timing, not on thesis)
- Held because: (a) position was sized as a small bet, (b) thesis was still valid
- Eventually: pivot announced, re-rating began
- Outcome: correct bet, imperfect investment (entry price not yet recovered)

---

## The River Tree Framework

The river tree is a **map of thematic waves** — not a portfolio tracker.

Each river represents one confirmed macro theme (AI infra, tech localization, etc.).
Each layer represents a position in the supply chain:

| Layer | Role | Typical behaviour |
|-------|------|-------------------|
| Source | Hyperscalers, capital allocators | Move first, confirm the theme |
| Upper | Primary technology suppliers | Move second, highest conviction |
| Middle | Bottleneck components | Highest alpha potential, most specific |
| Lower | Infrastructure enablers | Lag, but eventually re-rated |

**The hunting ground is the laggards within a confirmed layer.**

If the layer average is +80% over 1 year, but a structurally comparable node is +12%,
that node is a candidate. The question is: *why hasn't it moved?*

- If the reason is temporary (no news yet, less coverage, different fiscal year) → bet candidate
- If the reason is structural (different business model, losing market share) → skip

---

## What This Tool Should Help With

1. **Confirm the wave is real** — are the leaders actually moving? (price returns by layer)
2. **Find the laggards** — which nodes in a confirmed layer haven't caught up?
3. **Surface the catalyst context** — news, BBS sentiment, Minkabu analysis around the laggard
4. **Size the bet** — the tool should never suggest "buy this"; it surfaces candidates for the
   investor to research and decide on

---

## What This Tool Is NOT

- Not a buy/sell signal generator
- Not a price target tool
- Not a replacement for reading the actual news and filings
- Not optimized for day trading or short-term momentum

---

## Current Rivers

| River | Theme |
|-------|-------|
| `ai_infra` | AI Infrastructure Supercycle |
| `tech_local` | Tech Localization & Onshoring |
| `physical_ai` | Embodied Physical AI |
| `longevity` | Demographic Longevity |
