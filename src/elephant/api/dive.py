import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = "/panda-infra/elephant"
DIVES_DIR = Path(DATA_DIR) / "dives"

_jobs: dict[str, dict] = {}


def get_latest(ticker: str) -> dict | None:
    slug = ticker.replace(".", "_")
    files = sorted(DIVES_DIR.glob(f"*-{slug}.md"), reverse=True)
    if not files:
        return None
    f = files[0]
    date = f.stem.split("-" + slug)[0]
    return {
        "ticker": ticker,
        "date": date,
        "content": f.read_text(encoding="utf-8"),
        "storage_dir": str(DIVES_DIR),
    }


def list_dives() -> list[dict]:
    result = []
    for f in sorted(DIVES_DIR.glob("*.md"), reverse=True):
        parts = f.stem.rsplit("-", 1)
        if len(parts) == 2:
            date, slug = parts[0], parts[1]
            result.append({"ticker": slug.replace("_", "."), "date": date})
    return result


def run_dive(job_id: str, ticker: str) -> None:
    _jobs[job_id] = {"status": "running", "result": None, "error": None, "ticker": ticker}
    try:
        from elephant.diver import Diver
        from elephant.formatter import to_html
        from elephant.river.tree import RiverTree

        tree = RiverTree(os.path.join(DATA_DIR, "river_tree.json"))
        diver = Diver(DATA_DIR, tree=tree)
        brief = diver.dive(ticker)

        DIVES_DIR.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        slug = ticker.replace(".", "_")
        (DIVES_DIR / f"{date_str}-{slug}.md").write_text(brief, encoding="utf-8")
        (DIVES_DIR / f"{date_str}-{slug}.html").write_text(to_html(brief), encoding="utf-8")

        _jobs[job_id] = {"status": "done", "result": brief, "error": None, "ticker": ticker}
    except Exception as e:
        _jobs[job_id] = {"status": "error", "result": None, "error": str(e), "ticker": ticker}


def start_dive(ticker: str) -> str:
    from elephant.ticker_registry import normalize_ticker
    ticker = normalize_ticker(ticker)
    job_id = str(uuid.uuid4())
    t = threading.Thread(target=run_dive, args=(job_id, ticker), daemon=True)
    t.start()
    return job_id


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)
