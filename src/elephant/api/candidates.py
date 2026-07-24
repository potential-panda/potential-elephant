from functools import lru_cache
from time import time

from elephant.candidates import CandidateMetrics
from elephant.config import DATA_DIR, TICKERS_FILE, TREE_PATH


@lru_cache(maxsize=8)
def _cached_candidates(bucket: int) -> tuple[dict, ...]:
    return tuple(CandidateMetrics(DATA_DIR, TICKERS_FILE, tree_path=TREE_PATH).build())


def get_candidates(queue: str | None = None, include_suppressed: bool = False) -> list[dict]:
    rows = list(_cached_candidates(int(time() // 60)))
    if not include_suppressed:
        rows = [r for r in rows if r["queue"] != "suppressed"]
    if queue:
        rows = [r for r in rows if r["queue"] == queue.upper()]
    return rows
