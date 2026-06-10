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
            })
        rivers.append({
            "id": river.id,
            "name": river.name,
            "description": getattr(river, "description", ""),
            "nodes": nodes,
        })
    tree_file = os.path.join(DATA_DIR, "river_tree.json")
    return {"rivers": rivers, "layers": LAYERS, "file": tree_file}
