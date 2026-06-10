from elephant.candidates import CandidateMetrics
from elephant.config import DATA_DIR, TICKERS_FILE, TREE_PATH


def get_candidates(queue: str | None = None) -> list[dict]:
    rows = CandidateMetrics(DATA_DIR, TICKERS_FILE, tree_path=TREE_PATH).build()
    if queue:
        rows = [r for r in rows if r["queue"] == queue.upper()]
    return rows
