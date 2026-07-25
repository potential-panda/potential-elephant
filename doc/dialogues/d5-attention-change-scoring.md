# D5 Attention-Change Scoring Brief

## Purpose

Run a structured AgentOp dialogue that redesigns `score_d5` (the
`attention_change_score` dimension of the candidate score) so it works
sensibly for both JP and US tickers.

Recommended scenario:

- `/home/lulurun/workspace/agentop/src/agentop/dialogue/scenarios/explorer-critic.toml`

This dialogue is decision-only. Do not edit `potential-elephant` source files
during the dialogue. Produce a scoring spec that a separate implementation
pass can apply to `score_d5` and `scoring_config.py`.

This is research-score design, not investment advice. Do not produce buy,
sell, hold, price target, or trading recommendations.

## Why This Dialogue Exists

D5 is meant to capture "is attention to this name increasing" using Yahoo
Japan BBS (comment rank + comment velocity) and Minkabu coverage. It was
extended to cover US tickers, but a live check of the current dataset shows
the extension is broken in practice:

```text
59 US tickers checked
58 scored d5 = 0
1 scored d5 = 2  (WDC — Yahoo JP BBS presence bonus only)
```

Yahoo Japan BBS is a Japan-centric site. Most US tickers have no BBS page at
all (`has_yahoo_jp_bbs = False` or `None`), so almost every US name is
structurally capped near zero regardless of whether it is actually getting
hot among JP retail investors. The scoring needs to be redesigned, not just
patched.

## Project Context

Repository:

- `/home/lulurun/workspace/potential-elephant`

Relevant files to inspect (read these, do not assume from memory):

- `/home/lulurun/workspace/potential-elephant/src/elephant/scoring.py` —
  `score_d5()`, roughly lines 156-201.
- `/home/lulurun/workspace/potential-elephant/src/elephant/scoring_config.py`
  — `D5_*` constants, roughly lines 48-59.
- `/home/lulurun/workspace/potential-elephant/src/elephant/candidates.py` —
  `_load_bbs_signals()` (how `speed_latest`/`speed_prev`/`trend`/rank/
  `has_yahoo_jp_bbs` are computed from raw data) and the `score_d5(...)` call
  site around line 625.
- `/home/lulurun/workspace/potential-elephant/src/elephant/ticker_registry.py`
  — `get_yahoo_jp_bbs_status()`, how US tickers get probed for a Yahoo JP BBS
  page at all.
- `/home/lulurun/workspace/potential-elephant/doc/value_chain_framework.md` and
  `/home/lulurun/workspace/potential-elephant/STRATEGY.md` for the broader
  scoring philosophy (research-worthiness, not stock merit).
- Current uncommitted diff in this repo already touches US-ticker BBS
  handling (`git diff src/elephant/candidates.py src/elephant/scoring.py
  src/elephant/scoring_config.py src/elephant/yjp/harvester.py
  src/elephant/yjp/planner.py`) — read it to see work already in flight
  before proposing something that conflicts with it.

Useful commands:

```bash
cd /home/lulurun/workspace/potential-elephant/src
python -c "
from elephant.api.candidates import get_candidates
rows = get_candidates()
for r in rows:
    print(r['market'], r['ticker'], r.get('bbs_rank'), r.get('speed_latest'),
          r.get('speed_prev'), r.get('speed_trend'), r.get('has_yahoo_jp_bbs'),
          'd5=', r.get('d5_attention_change'))
"
```

Use this (or similar ad-hoc queries against `CandidateMetrics`) to ground
every claim in real current data — JP and US side by side — rather than
hypothetical examples.

## Hints From the Product Owner

These are starting hypotheses to investigate and stress-test, not settled
answers:

1. **Velocity matters, and so does change of velocity.** The current model
   only checks one week-over-week velocity delta against a fixed +20%
   threshold (`D5_BBS_VELOCITY_THRESHOLD`) for a flat +2. Consider whether
   acceleration (is velocity itself speeding up across more than two points,
   not just one WoW comparison) deserves its own signal, separate from raw
   velocity level.
2. **US vs JP needs an asymmetric baseline, not a shared bar.** Yahoo Japan
   BBS is a JP-investor site, so JP names get talked about by default and US
   names rarely do. A US ticker that *is* being discussed is a stronger
   signal than the same absolute comment count would be for a JP ticker, and
   a US ticker with *no* discussion should not be punished as hard as a JP
   ticker with no discussion, because "not discussed" is the expected default
   for most US names. Decide concretely how much reward presence/activity
   should get for US tickers, and whether/how much absence should cost —
   if anything.

## Design Questions

The dialogue should resolve all of these with a concrete formula, not just
prose:

1. **Velocity definition.** Is comments/hour (current `speed_latest`) the
   right unit? Should it be normalized (e.g., relative to the ticker's own
   trailing baseline, or relative to typical US vs JP volume) before
   thresholding?
2. **Change-of-velocity / acceleration.** How should a multi-point trend
   (more than two BBS speed observations) translate into points, distinct
   from the existing single WoW velocity check? Should deceleration also
   matter (penalize fading attention, or just withhold points)?
3. **Rank-based signal for tickers with no rank.** The current `+4` rank-
   improvement bonus requires 3 consecutive ranked days
   (`bbs_rank_history`), which barely exists for US tickers. What should
   stand in for "improving attention" when there is no rank series?
4. **Presence/activity reward for US tickers.** Today: flat
   `D5_US_BBS_PRESENCE_PTS=2` for having any Yahoo JP BBS page, plus
   `D5_US_BBS_ACTIVE_PTS=2` if `speed_latest >= D5_US_BBS_ACTIVE_THRESHOLD`
   (5.0 comments/hour). Are these thresholds and point values defensible
   against the actual distribution of US ticker velocities seen in the live
   data, or arbitrary?
5. **Absence penalty (or lack thereof) for US tickers.** Should a US ticker
   with no BBS page ever score below a US ticker with a quiet BBS page? Should
   it differ from how a JP ticker with no/low BBS attention is scored?
6. **Cap interactions.** `D5_BBS_CAP=6` (BBS-derived points) and
   `D5_MAX=10` (with Minkabu-new-coverage `+3`). Should the cap or max differ
   by market, or stay shared with different point sources feeding into it?
7. **Minkabu interplay.** `D5_MINKABU_NEW_PTS=3` only fires for
   newly-initiated Minkabu coverage — does this interact sensibly with BBS
   points for both markets, or should Minkabu weight differ by market too
   (Minkabu is also JP-centric)?
8. **Decay/freshness.** Should attention signals decay if the underlying
   `speed_history` data is stale (e.g., a `has_yahoo_jp_bbs=True` ticker that
   hasn't had a comment in weeks)?

## Required Deliverables

Create these files in the AgentOp dialogue working directory under
`deliverables/`.

### `d5-scoring-decision.md`

- Executive summary of what changes and why.
- Final formula for `score_d5`, expressed precisely enough to translate
  directly into Python (inputs, point values, thresholds, caps, order of
  operations).
- Explicit US-vs-JP asymmetry rule, stated as a rule, not just examples.
- At least 3 worked examples computed against real current data: one JP
  ticker, one actively-discussed US ticker (e.g. WDC), one US ticker with no
  Yahoo JP BBS presence — showing old score vs proposed new score for each.
- Residual risks and known limitations (e.g., thin US BBS sample size,
  noisy small-N velocity).
- Explicit statement that this is not investment advice.

### `d5-change-set.md`

Actionable change list in this format:

```markdown
## Apply

| Constant / Function | Current | Proposed | Reason |
|---|---|---|---|

## New Inputs Needed

| Field | Source | Why score_d5 needs it | Already available? |
|---|---|---|---|

## Human Judgment Required

| Question | Why It Matters | Suggested Decision |
|---|---|---|
```

Each `Apply` row must be precise enough for a later implementation agent to
edit `src/elephant/scoring.py` and `src/elephant/scoring_config.py` directly.

## Acceptance Criteria

The final dialogue output is acceptable only if:

- Every claim about current behavior is grounded in the actual code/data,
  not assumption (cite file + line, or a command output).
- The proposed formula only uses fields that exist today in
  `_load_bbs_signals()` / candidate rows, or explicitly lists what new field
  would need to be harvested and from where.
- The US-vs-JP asymmetry has a stated, numeric rule — not just "US should get
  more credit."
- Velocity *and* change-of-velocity are both addressed as distinct signals.
- The worked examples use real tickers and real current values from this
  repo's data, not invented numbers.
- No buy/sell/hold/price-target language appears.
- The proposal stays within D5's role (attention-change signal feeding a
  0-10 dimension of `compute_final_score`) — it must not turn into a general
  re-architecture of D1-D6 or the queue system.

## Dialogue-Specific Challenge Criteria

The Critic should specifically challenge:

- Any threshold or point value that isn't justified against the actual
  distribution of values in the live dataset.
- Asymmetry rules that are hand-wavy rather than a concrete formula.
- Proposals that would make US tickers score *higher* than JP tickers purely
  because the JP site structurally under-covers US names, without genuine
  evidence of attention.
- Proposals that require data this repo does not currently harvest, without
  flagging it explicitly as a new requirement.
- Worked examples that use round/invented numbers instead of pulling from
  `get_candidates()` or the underlying parquet/cache data.
