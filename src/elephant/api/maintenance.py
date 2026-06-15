from elephant import maintenance as _maintenance
from elephant.config import TREE_PATH


def get_maintenance_items() -> list[dict]:
    return _maintenance.generate(tree_path=TREE_PATH)


def resolve_item(maintenance_id: str, action: str, reason: str = "") -> dict:
    return _maintenance.resolve(maintenance_id, action=action, reason=reason, tree_path=TREE_PATH)
