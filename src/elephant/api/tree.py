import os

from elephant.config import DATA_DIR


def get_tree() -> dict:
    from elephant.river.tree import LAYERS, RiverTree
    tree = RiverTree(os.path.join(DATA_DIR, "river_tree.json"))
    rivers = []
    for river in tree.list_rivers():
        nodes = []
        for node in river.nodes:
            nodes.append({
                "ticker": node.ticker,
                "layer": node.layer,
                "name": node.name,
                "market": node.market,
                "role": node.role,
                "notes": getattr(node, "notes", ""),
                "added": node.added,
                "source": getattr(node, "source", "manual"),
                # lifecycle fields
                "status": node.status,
                "thesis": node.thesis,
                "counterarguments": node.counterarguments,
                "confidence": node.confidence,
                "last_reviewed": node.last_reviewed,
                "next_review_cadence": node.next_review_cadence,
                "what_would_change_our_mind": node.what_would_change_our_mind,
                "last_human_decision": node.last_human_decision,
                "last_human_decision_date": node.last_human_decision_date,
                "evidence_refs": node.evidence_refs,
                "primary_river": node.primary_river,
                "peer_group": node.peer_group,
                "causal_edge": node.causal_edge,
                "behind_reason": node.behind_reason,
                "competitor_tickers": node.competitor_tickers,
                "leader_tickers": node.leader_tickers,
            })
        rivers.append({
            "id": river.id,
            "name": river.name,
            "description": getattr(river, "description", ""),
            "status": getattr(river, "status", "active"),
            "nodes": nodes,
        })
    tree_file = os.path.join(DATA_DIR, "river_tree.json")
    return {"rivers": rivers, "layers": LAYERS, "file": tree_file}
