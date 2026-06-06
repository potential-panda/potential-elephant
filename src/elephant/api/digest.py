import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = "/panda-infra/elephant"
TICKERS_FILE = "/panda-infra/elephant/tickers.txt"

_jobs: dict[str, dict] = {}


def get_latest() -> dict | None:
    digests_dir = Path(DATA_DIR) / "digests"
    files = sorted(digests_dir.glob("*.md"), reverse=True)
    if not files:
        return None
    f = files[0]
    return {
        "date": f.stem,
        "content": f.read_text(encoding="utf-8"),
    }


def list_digests() -> list[dict]:
    digests_dir = Path(DATA_DIR) / "digests"
    result = []
    for f in sorted(digests_dir.glob("*.md"), reverse=True):
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

        digests_dir = Path(DATA_DIR) / "digests"
        digests_dir.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        (digests_dir / f"{date_str}.md").write_text(digest, encoding="utf-8")

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
