import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from elephant.config import DATA_DIR


RUN_LOG_FILE = Path(DATA_DIR) / "source_runs.jsonl"


@dataclass
class SourceRun:
    run_id: str
    kind: str
    source_id: str
    scope: str
    ticker: str | None
    url: str | None
    status: str
    started_at: str
    finished_at: str
    row_count: int = 0
    error: str | None = None


def start_run(kind: str, source_id: str, scope: str, ticker: str | None = None, url: str | None = None) -> dict:
    return {
        "run_id": uuid4().hex,
        "kind": kind,
        "source_id": source_id,
        "scope": scope,
        "ticker": ticker,
        "url": url,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }


def finish_run(run: dict, status: str, row_count: int = 0, error: str | None = None, path: Path = RUN_LOG_FILE) -> SourceRun:
    record = SourceRun(
        run_id=run["run_id"],
        kind=run["kind"],
        source_id=run["source_id"],
        scope=run["scope"],
        ticker=run.get("ticker"),
        url=run.get("url"),
        status=status,
        started_at=run["started_at"],
        finished_at=datetime.now().isoformat(timespec="seconds"),
        row_count=row_count,
        error=error,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    return record


def recent_runs(limit: int = 100, path: Path = RUN_LOG_FILE) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    result = []
    for line in lines:
        try:
            result.append(json.loads(line))
        except Exception:
            continue
    return result

