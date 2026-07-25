# Monthly Atlas Review Brief

## Purpose

Run a structured AgentOp dialogue that reviews Potential Elephant's atlas
for correctness, freshness, and scoring hygiene.

Recommended scenario:

- `/home/lulurun/workspace/agentop/src/agentop/dialogue/scenarios/explorer-critic.toml`

The output is a reviewed maintenance decision. Do not edit the atlas during the
dialogue unless the operator explicitly changes this brief to request edits.

This is research taxonomy maintenance, not investment advice. Do not produce
buy, sell, hold, price target, portfolio sizing, or trading recommendations.

## Project Context

Repository:

- `/home/lulurun/workspace/potential-elephant`

Current persistent data:

- Atlas: `/panda-infra/elephant/atlas.json`
- Data dir: `/panda-infra/elephant`

Relevant project files to inspect:

- `/home/lulurun/workspace/potential-elephant/README.md`
- `/home/lulurun/workspace/potential-elephant/STRATEGY.md`
- `/home/lulurun/workspace/potential-elephant/doc/value_chain_framework.md`
- `/home/lulurun/workspace/potential-elephant/src/elephant/value_chain/atlas.py`
- `/home/lulurun/workspace/potential-elephant/src/elephant/candidates.py`
- `/home/lulurun/workspace/potential-elephant/src/elephant/scoring.py`
- `/panda-infra/elephant/atlas.json`

Useful commands:

```bash
cd /home/lulurun/workspace/potential-elephant
PYTHONPATH=src python src/cli.py atlas show
PYTHONPATH=src python - <<'PY'
import json
from elephant.config import ATLAS_PATH
data = json.load(open(ATLAS_PATH))
for value_chain in data.get("value_chains", []):
    counts, statuses = {}, {}
    for company in value_chain.get("companies", []):
        counts[company.get("stage")] = counts.get(company.get("stage"), 0) + 1
        statuses[company.get("status", "active")] = statuses.get(company.get("status", "active"), 0) + 1
    print(value_chain["id"], len(value_chain.get("companies", [])), counts, statuses)
PY
```

## Review Scope

Review every value_chain and company currently in the atlas.

For each value_chain:

- confirm the value_chain still has a clear thematic thesis
- check whether each stage has coherent comparable companies
- identify overbroad proxies, stale companies, duplicate companies, and metadata issues
- identify missing high-confidence companies only when evidence-backed

For each company:

- verify ticker, market, name, stage, status, role, and `primary_value_chain`
- decide whether current status should remain or change
- decide whether stage placement is correct
- check whether the company is a true supply-chain company or merely theme-adjacent
- check whether current source evidence supports the role

## Company Lifecycle Rules

Use these statuses strictly:

- `active`: clear, current, evidence-backed supply-chain role; useful for peer/stage scoring.
- `weak`: relevant but indirect, stale, financially impaired, or execution-risk-heavy.
- `watch`: plausible but not ready to influence scoring strongly.
- `dormant`: preserved context, ETF/proxy, broad macro exposure, stale thesis, or theme-adjacent name that should not influence scoring.
- `rejected`: reviewed and intentionally not a fit.

Scoring hygiene rule:

- Only `active` and `weak` companies should influence active peer/stage scoring.
- `watch` may appear in monitoring surfaces, but should not be treated as fully comparable.
- `dormant` and `rejected` should not influence daily candidate scoring.

## Evidence Rules

Use current sources when freshness matters.

Preferred evidence:

- company investor relations, official product pages, official news releases
- securities filings, exchange disclosures, TDnet/company disclosures
- government or regulatory program pages
- official partnership announcements

Secondary evidence may be used only as context:

- reputable financial press
- trade press
- analyst summaries

Do not use these as proof of value_chain fit:

- Yahoo BBS heat
- social media
- generic theme articles
- price movement alone
- ETF inclusion alone

## Required Deliverables

Create these files in the AgentOp dialogue working directory under
`deliverables/`.

### `atlas-review-decision.md`

Final reviewed decision for the month.

Include:

- review date
- value_chains reviewed
- executive summary
- high-confidence keep decisions
- proposed downgrades
- proposed promotions
- proposed stage moves
- proposed dormant/rejected changes
- duplicate and metadata fixes
- missing-company candidates that need human review
- residual risks
- explicit statement that this is not investment advice

### `atlas-change-set.md`

Actionable change list.

Use this format:

```markdown
## Apply

| Action | Value Chain | Ticker | From | To | Reason |
|---|---|---|---|---|---|

## Do Not Apply Yet

| Candidate | Value Chain | Proposed Action | Missing Evidence |
|---|---|---|---|

## Human Judgment Required

| Question | Why It Matters | Suggested Decision |
|---|---|---|
```

Each `Apply` row must be precise enough for a later agent to update
`/panda-infra/elephant/atlas.json`.

### `evidence-log.md`

Evidence used for decisions.

Use this format:

```markdown
| Ticker | Value Chain | Claim Checked | Evidence Source | Evidence Type | Freshness | Conclusion |
|---|---|---|---|---|---|---|
```

Evidence type examples:

- primary/company
- filing/disclosure
- government/regulatory
- trade press
- financial press
- unresolved

## Acceptance Criteria

The final dialogue output is acceptable only if:

- all current value_chains were inspected
- all required deliverables exist
- same-value_chain duplicates were checked
- ticker market metadata was checked
- every proposed change has a reason and evidence basis
- promotions to `active` use stronger evidence than downgrades
- ETF/proxy/theme-adjacent companies are not left active without explicit reason
- residual risks are documented
- no buy/sell/hold language appears

## Dialogue-Specific Challenge Criteria

The Critic should specifically challenge:

- unsupported promotions to `active`
- same-value_chain duplicates that would distort scoring
- cross-value_chain duplicates that lack a clear `primary_value_chain` rationale
- stale or speculative companies left as active
- ETFs, broad proxies, and theme-adjacent names left in active scoring
- metadata mismatches such as `.T` tickers not marked `JP`
- evidence that relies on price movement, BBS heat, or generic theme articles
- final change rows that are not precise enough to apply safely
