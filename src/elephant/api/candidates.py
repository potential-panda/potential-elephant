import os
from elephant.candidates import CandidateMetrics

DATA_DIR = "/panda-infra/elephant"
TICKERS_FILE = os.path.join(DATA_DIR, "tickers.txt")
TREE_PATH = os.path.join(DATA_DIR, "river_tree.json")


def get_candidates(queue: str | None = None) -> list[dict]:
    rows = CandidateMetrics(DATA_DIR, TICKERS_FILE, tree_path=TREE_PATH).build()
    if queue:
        rows = [r for r in rows if r["queue"] == queue.upper()]
    return rows
