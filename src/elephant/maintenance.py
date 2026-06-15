"""
Queue D — tree maintenance item generation and resolution log.

Items are generated from current river tree state. A resolved item is hidden
until the underlying trigger fingerprint changes (meaning the tree state that
caused the trigger has changed enough to warrant a fresh review).
"""

import hashlib
import json
import os
from datetime import date, datetime
from typing import Optional

from elephant.config import DATA_DIR, TREE_PATH

RESOLUTIONS_FILE = os.path.join(DATA_DIR, "maintenance_resolutions.json")
STALE_NODE_DAYS = 90


def _stable_id(key: str) -> str:
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _fingerprint(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()[:16]


def _load_resolutions() -> dict:
    if not os.path.exists(RESOLUTIONS_FILE):
        return {}
    try:
        return json.loads(open(RESOLUTIONS_FILE, encoding="utf-8").read())
    except Exception:
        return {}


def _save_resolutions(data: dict) -> None:
    os.makedirs(os.path.dirname(RESOLUTIONS_FILE), exist_ok=True)
    with open(RESOLUTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate(tree_path: Optional[str] = None) -> list[dict]:
    """Generate all active Queue D maintenance items from tree state."""
    if tree_path is None:
        tree_path = TREE_PATH

    from elephant.river.tree import LAYERS, RiverTree

    tree = RiverTree(tree_path)
    resolutions = _load_resolutions()
    items = []
    ticker_rivers: dict[str, list[str]] = {}

    for river in tree.list_rivers():
        by_layer: dict[str, list] = {layer: [] for layer in LAYERS}
        for node in river.nodes:
            if node.layer in by_layer:
                by_layer[node.layer].append(node)
            ticker_rivers.setdefault(node.ticker, []).append(river.id)

        for layer, nodes in by_layer.items():
            active_weak = [n for n in nodes if n.status in ("active", "weak")]

            # thin_layer: fewer than 3 active/weak nodes in this layer
            if len(active_weak) < 3:
                key = f"thin_layer:{river.id}:{layer}"
                mid = _stable_id(key)
                fp = _fingerprint(f"{key}:{len(active_weak)}:{','.join(sorted(n.ticker for n in active_weak))}")
                if resolutions.get(mid, {}).get("trigger_fingerprint") != fp:
                    items.append({
                        "maintenance_id": mid,
                        "trigger_type": "thin_layer",
                        "trigger_fingerprint": fp,
                        "river_id": river.id,
                        "river_name": river.name,
                        "layer": layer,
                        "ticker": None,
                        "priority": "medium",
                        "reason": f"Layer {layer!r} in {river.name!r} has {len(active_weak)} active/weak node(s) — minimum is 3",
                        "recommended_actions": [
                            "Review and add nodes to this layer",
                            "Or resolve as intentional if the layer is purposefully thin",
                        ],
                        "context": {
                            "active_weak_count": len(active_weak),
                            "all_nodes": [n.ticker for n in nodes],
                        },
                    })

            for node in nodes:
                # stale_node: not reviewed in > STALE_NODE_DAYS for active/weak/watch
                if node.status in ("active", "weak", "watch"):
                    stale = False
                    days_since: Optional[int] = None
                    if node.last_reviewed:
                        try:
                            last_rev = datetime.strptime(node.last_reviewed, "%Y-%m-%d").date()
                            days_since = (date.today() - last_rev).days
                            stale = days_since > STALE_NODE_DAYS
                        except ValueError:
                            stale = True
                    else:
                        stale = True

                    if stale:
                        key = f"stale_node:{river.id}:{node.ticker}"
                        mid = _stable_id(key)
                        fp = _fingerprint(f"{key}:{node.status}:{node.last_reviewed or 'never'}")
                        if resolutions.get(mid, {}).get("trigger_fingerprint") != fp:
                            label = f"{days_since} days" if days_since is not None else "never"
                            items.append({
                                "maintenance_id": mid,
                                "trigger_type": "stale_node",
                                "trigger_fingerprint": fp,
                                "river_id": river.id,
                                "river_name": river.name,
                                "layer": node.layer,
                                "ticker": node.ticker,
                                "priority": "low",
                                "reason": f"{node.ticker} ({node.status}) last reviewed {label} ago — threshold is {STALE_NODE_DAYS} days",
                                "recommended_actions": [
                                    "Review thesis and update last_reviewed date",
                                    "Or demote to dormant if monitoring value has faded",
                                ],
                                "context": {
                                    "status": node.status,
                                    "last_reviewed": node.last_reviewed,
                                    "days_since_review": days_since,
                                },
                            })

                # proposed_node: node awaiting approve/reject
                if node.status == "proposed":
                    key = f"proposed_node:{river.id}:{node.ticker}"
                    mid = _stable_id(key)
                    fp = _fingerprint(f"{key}:{node.added}:{node.source}")
                    if resolutions.get(mid, {}).get("trigger_fingerprint") != fp:
                        items.append({
                            "maintenance_id": mid,
                            "trigger_type": "proposed_node",
                            "trigger_fingerprint": fp,
                            "river_id": river.id,
                            "river_name": river.name,
                            "layer": node.layer,
                            "ticker": node.ticker,
                            "priority": "high",
                            "reason": f"{node.ticker} is proposed in {river.name!r} and awaiting human decision",
                            "recommended_actions": [
                                "Approve: set status=active, add thesis and what_would_change_our_mind",
                                "Reject: set status=rejected with reason",
                            ],
                            "context": {
                                "added": node.added,
                                "source": node.source,
                                "thesis": node.thesis,
                            },
                        })

                # missing_what_would_change_our_mind: active/weak/watch without falsification condition
                if node.status in ("active", "weak", "watch") and not node.what_would_change_our_mind:
                    key = f"missing_falsification:{river.id}:{node.ticker}"
                    mid = _stable_id(key)
                    fp = _fingerprint(f"{key}:{node.status}:missing")
                    if resolutions.get(mid, {}).get("trigger_fingerprint") != fp:
                        items.append({
                            "maintenance_id": mid,
                            "trigger_type": "missing_what_would_change_our_mind",
                            "trigger_fingerprint": fp,
                            "river_id": river.id,
                            "river_name": river.name,
                            "layer": node.layer,
                            "ticker": node.ticker,
                            "priority": "medium",
                            "reason": f"{node.ticker} ({node.status}) has no falsification condition — required for active monitoring",
                            "recommended_actions": [
                                "Add what_would_change_our_mind to define the thesis exit condition",
                            ],
                            "context": {
                                "status": node.status,
                                "thesis": node.thesis,
                            },
                        })

    # multi_river_conflict: same ticker in multiple rivers
    for ticker, river_ids in ticker_rivers.items():
        if len(river_ids) > 1:
            key = f"multi_river_conflict:{ticker}"
            mid = _stable_id(key)
            fp = _fingerprint(f"{key}:{','.join(sorted(river_ids))}")
            if resolutions.get(mid, {}).get("trigger_fingerprint") != fp:
                items.append({
                    "maintenance_id": mid,
                    "trigger_type": "multi_river_conflict",
                    "trigger_fingerprint": fp,
                    "river_id": None,
                    "river_name": None,
                    "layer": None,
                    "ticker": ticker,
                    "priority": "medium",
                    "reason": f"{ticker} appears in {len(river_ids)} rivers: {', '.join(sorted(river_ids))}",
                    "recommended_actions": [
                        "Set primary_river=True on the primary assignment",
                        "Or remove from secondary rivers if the overlap is not intentional",
                    ],
                    "context": {"river_ids": sorted(river_ids)},
                })

    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: priority_order.get(x["priority"], 3))
    return items


def resolve(maintenance_id: str, action: str, reason: str = "", tree_path: Optional[str] = None) -> dict:
    """Record a resolution for a Queue D item.

    The item must currently appear in generate() — stale resolutions are rejected
    so that a resolved item cannot be hidden forever after its fingerprint changes.
    """
    items = generate(tree_path)
    item = next((i for i in items if i["maintenance_id"] == maintenance_id), None)
    if item is None:
        raise ValueError(
            f"Queue D item {maintenance_id!r} not found or already resolved with current tree state"
        )

    resolutions = _load_resolutions()
    entry = {
        "maintenance_id": maintenance_id,
        "trigger_fingerprint": item["trigger_fingerprint"],
        "action": action,
        "reason": reason,
        "resolved_at": date.today().isoformat(),
    }
    resolutions[maintenance_id] = entry
    _save_resolutions(resolutions)
    return entry


def list_resolutions() -> list[dict]:
    return list(_load_resolutions().values())
