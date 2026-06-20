# AgentOp Dialogues

This directory stores reusable AgentOp dialogue instructions for Potential
Elephant.

The scenario should stay generic. The project-specific topic, evidence rules,
and deliverable requirements live in the brief.

For monthly tree maintenance, use AgentOp's built-in `explorer-critic`
scenario: one agent explores/proposes a grounded decision, and the other
verifies/challenges it against the same sources.

## Monthly River Tree Review

Run from the AgentOp repo or from any shell where `agentop` is installed:

```bash
agentop dialogue start \
  --agent-a codex \
  --agent-b codex \
  --brief /home/lulurun/workspace/potential-elephant/doc/dialogues/monthly-tree-review.md \
  --scenario /home/lulurun/workspace/agentop/src/agentop/dialogue/scenarios/explorer-critic.toml
```

The dialogue writes its working files under:

```text
~/.agent-dashboard/dialogues/
```

The final decision should be in that dialogue directory:

```text
deliverables/tree-review-decision.md
deliverables/tree-change-set.md
deliverables/evidence-log.md
```

The dialogue is intentionally decision-only by default. After reviewing the
deliverables, ask an implementation agent to apply the approved change set to:

```text
/panda-infra/elephant/river_tree.json
```

## Optional Variants

Use different agents if useful:

```bash
agentop dialogue start \
  --agent-a claude \
  --agent-b codex \
  --brief /home/lulurun/workspace/potential-elephant/doc/dialogues/monthly-tree-review.md \
  --scenario /home/lulurun/workspace/agentop/src/agentop/dialogue/scenarios/explorer-critic.toml
```

Use `--max-turns` for a shorter or longer review:

```bash
agentop dialogue start \
  --agent-a codex \
  --agent-b codex \
  --max-turns 40 \
  --brief /home/lulurun/workspace/potential-elephant/doc/dialogues/monthly-tree-review.md \
  --scenario /home/lulurun/workspace/agentop/src/agentop/dialogue/scenarios/explorer-critic.toml
```
