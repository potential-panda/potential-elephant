import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

from elephant.config import DATA_DIR, TICKERS_FILE

_jobs: dict[str, dict] = {}


DIGESTS_DIR = Path(DATA_DIR) / "digests"


def _digest_path() -> Path:
    return DIGESTS_DIR


def get_latest() -> dict | None:
    files = sorted(DIGESTS_DIR.glob("*.md"), reverse=True)
    if not files:
        return None
    f = files[0]
    return {
        "date": f.stem,
        "content": f.read_text(encoding="utf-8"),
        "path": str(f),
        "storage_dir": str(DIGESTS_DIR),
    }


def get_by_date(date: str) -> dict | None:
    f = DIGESTS_DIR / f"{date}.md"
    if not f.exists():
        return None
    return {
        "date": f.stem,
        "content": f.read_text(encoding="utf-8"),
        "path": str(f),
        "storage_dir": str(DIGESTS_DIR),
    }


def list_digests() -> list[dict]:
    result = []
    for f in sorted(DIGESTS_DIR.glob("*.md"), reverse=True):
        result.append({"date": f.stem, "size": f.stat().st_size})
    return result


def generate_digest(job_id: str) -> None:
    _jobs[job_id] = {"status": "running", "result": None, "error": None}
    try:
        from elephant.river.tree import RiverTree
        from elephant.synthesizer import Synthesizer
        tree_path = os.path.join(DATA_DIR, "river_tree.json")
        tree = RiverTree(tree_path)
        synth = Synthesizer(DATA_DIR, TICKERS_FILE, tree=tree)
        digest = synth.generate()

        DIGESTS_DIR.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        (DIGESTS_DIR / f"{date_str}.md").write_text(digest, encoding="utf-8")

        _jobs[job_id] = {"status": "done", "result": digest, "error": None}
    except Exception as e:
        _jobs[job_id] = {"status": "error", "result": None, "error": str(e)}


def start_generate() -> str:
    job_id = str(uuid.uuid4())
    t = threading.Thread(target=generate_digest, args=(job_id,), daemon=True)
    t.start()
    return job_id


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)
