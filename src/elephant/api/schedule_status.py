import os
import subprocess
from datetime import datetime

from elephant.config import DATA_DIR

_LOG_FILE = os.path.join(DATA_DIR, "scheduler.log")


def get_status() -> dict:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", "elephant-scheduler.service",
             "--property=ActiveState,SubState,MainPID,ActiveEnterTimestamp,LoadState"],
            capture_output=True, text=True, timeout=5,
        )
        props = {}
        for line in result.stdout.strip().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                props[k] = v

        active = props.get("ActiveState", "unknown")
        sub = props.get("SubState", "unknown")
        pid = props.get("MainPID", "0")
        since_raw = props.get("ActiveEnterTimestamp", "")
        since = None
        if since_raw and since_raw != "n/a":
            try:
                since = since_raw.strip()
            except Exception:
                pass

        return {
            "active": active == "active",
            "state": f"{active} ({sub})",
            "pid": int(pid) if pid.isdigit() else None,
            "since": since,
            "log_file": _LOG_FILE,
        }
    except Exception as e:
        return {"active": False, "state": "error", "pid": None, "since": None,
                "error": str(e), "log_file": "/panda-infra/elephant/scheduler.log"}


def get_dry_run_plan() -> list[dict]:
    try:
        result = subprocess.run(
            ["python", "src/cli.py", "schedule", "--dry-run"],
            capture_output=True, text=True, timeout=30,
        )
        tasks = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if " - " in line and ":" in line.split(" - ")[0]:
                parts = line.split(" - ", 1)
                tasks.append({"time": parts[0].strip(), "label": parts[1].strip()})
        return tasks
    except Exception:
        return []
