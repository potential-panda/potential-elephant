# Monthly River Tree Review Brief

## Purpose

Run a structured AgentOp dialogue that reviews Potential Elephant's river tree
for correctness, freshness, and scoring hygiene.

Recommended scenario:

- `/home/lulurun/workspace/agentop/src/agentop/dialogue/scenarios/explorer-critic.toml`

The output is a reviewed maintenance decision. Do not edit the tree during the
dialogue unless the operator explicitly changes this brief to request edits.

This is research taxonomy maintenance, not investment advice. Do not produce
buy, sell, hold, price target, portfolio sizing, or trading recommendations.

## Project Context

Repository:

- `/home/lulurun/workspace/potential-elephant`

Current persistent data:

- Tree: `/panda-infra/elephant/river_tree.json`
- Data dir: `/panda-infra/elephant`

Relevant project files to inspect:

- `/home/lulurun/workspace/potential-elephant/README.md`
- `/home/lulurun/workspace/potential-elephant/STRATEGY.md`
- `/home/lulurun/workspace/potential-elephant/doc/river_framework.md`
- `/home/lulurun/workspace/potential-elephant/src/elephant/river/tree.py`
- `/home/lulurun/workspace/potential-elephant/src/elephant/candidates.py`
- `/home/lulurun/workspace/potential-elephant/src/elephant/scoring.py`
- `/panda-infra/elephant/river_tree.json`

Useful commands:

```bash
cd /home/lulurun/workspace/potential-elephant
PYTHONPATH=src python src/cli.py tree show
PYTHONPATH=src python - <<'PY'
import json
from elephant.config import TREE_PATH
data = json.load(open(TREE_PATH))
for river in data.get("rivers", []):
    counts, statuses = {}, {}
    for node in river.get("nodes", []):
        counts[node.get("layer")] = counts.get(node.get("layer"), 0) + 1
        statuses[node.get("status", "active")] = statuses.get(node.get("status", "active"), 0) + 1
    print(river["id"], len(river.get("nodes", [])), counts, statuses)
PY
```

## Review Scope

Review every river and node currently in the tree.

For each river:

- confirm the river still has a clear thematic thesis
- check whether each layer has coherent comparable nodes
- identify overbroad proxies, stale nodes, duplicate nodes, and metadata issues
- identify missing high-confidence nodes only when source-backed

For each node:

- verify ticker, market, name, layer, status, role, and `primary_river`
- decide whether current status should remain or change
- decide whether layer placement is correct
- check whether the node is a true supply-chain node or merely theme-adjacent
- check whether current source evidence supports the role

## Node Lifecycle Rules

Use these statuses strictly:

- `active`: clear, current, source-backed supply-chain role; useful for peer/layer scoring.
- `weak`: relevant but indirect, stale, financially impaired, or execution-risk-heavy.
- `watch`: plausible but not ready to influence scoring strongly.
- `dormant`: preserved context, ETF/proxy, broad macro exposure, stale thesis, or theme-adjacent name that should not influence scoring.
- `rejected`: reviewed and intentionally not a fit.

Scoring hygiene rule:

- Only `active` and `weak` nodes should influence active peer/layer scoring.
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

Do not use these as proof of river fit:

- Yahoo BBS heat
- social media
- generic theme articles
- price movement alone
- ETF inclusion alone

## Required Deliverables

Create these files in the AgentOp dialogue working directory under
`deliverables/`.

### `tree-review-decision.md`

Final reviewed decision for the month.

Include:

- review date
- rivers reviewed
- executive summary
- high-confidence keep decisions
- proposed downgrades
- proposed promotions
- proposed layer moves
- proposed dormant/rejected changes
- duplicate and metadata fixes
- missing-node candidates that need human review
- residual risks
- explicit statement that this is not investment advice

### `tree-change-set.md`

Actionable change list.

Use this format:

```markdown
## Apply

| Action | River | Ticker | From | To | Reason |
|---|---|---|---|---|---|

## Do Not Apply Yet

| Candidate | River | Proposed Action | Missing Evidence |
|---|---|---|---|

## Human Judgment Required

| Question | Why It Matters | Suggested Decision |
|---|---|---|
```

Each `Apply` row must be precise enough for a later agent to update
`/panda-infra/elephant/river_tree.json`.

### `evidence-log.md`

Evidence used for decisions.

Use this format:

```markdown
| Ticker | River | Claim Checked | Evidence Source | Evidence Type | Freshness | Conclusion |
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

- all current rivers were inspected
- all required deliverables exist
- same-river duplicates were checked
- ticker market metadata was checked
- every proposed change has a reason and evidence basis
- promotions to `active` use stronger evidence than downgrades
- ETF/proxy/theme-adjacent nodes are not left active without explicit reason
- residual risks are documented
- no buy/sell/hold language appears

## Dialogue-Specific Challenge Criteria

The Critic should specifically challenge:

- unsupported promotions to `active`
- same-river duplicates that would distort scoring
- cross-river duplicates that lack a clear `primary_river` rationale
- stale or speculative nodes left as active
- ETFs, broad proxies, and theme-adjacent names left in active scoring
- metadata mismatches such as `.T` tickers not marked `JP`
- evidence that relies on price movement, BBS heat, or generic theme articles
- final change rows that are not precise enough to apply safely
