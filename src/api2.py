import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import elephant.secrets as _secrets

_secrets.load()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess

from elephant.source.catalog import get_source, list_sources
from elephant.source.registry import SourceRegistry
from elephant.source.run_log import recent_runs
from elephant.source.scheduler import create_daily_plan
from elephant.ticker_registry import normalize_ticker

app = FastAPI(title="Elephant Source API v2", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SourceCheckRequest(BaseModel):
    ticker: str
    source_id: str | None = None


@app.get("/api2/sources")
def api2_sources(scope: str | None = Query(None, pattern="^(market|ticker)$")):
    return [s.to_dict() for s in list_sources(scope=scope)]


@app.get("/api2/sources/{source_id}")
def api2_source(source_id: str):
    try:
        return get_source(source_id).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api2/source-registry")
def api2_registry():
    registry = SourceRegistry()
    return registry.data


@app.get("/api2/source-registry/{ticker}")
def api2_registry_ticker(ticker: str):
    registry = SourceRegistry()
    canonical = normalize_ticker(ticker)
    return {"ticker": canonical, **registry.get_ticker(canonical)}


@app.get("/api2/source-plan")
def api2_source_plan(ticker: str | None = None, source_id: str | None = None):
    tasks = create_daily_plan()
    if ticker:
        canonical = normalize_ticker(ticker)
        tasks = [t for t in tasks if t.ticker == canonical]
    if source_id:
        tasks = [t for t in tasks if t.source_id == source_id]
    return [
        {
            "source_id": t.source_id,
            "scope": t.scope,
            "ticker": t.ticker,
            "url": t.url,
            "scheduled_at": t.scheduled_at.isoformat(),
            "args": t.args or {},
        }
        for t in tasks
    ]


@app.get("/api2/source-scheduler/plan")
def api2_source_scheduler_plan(ticker: str | None = None, source_id: str | None = None):
    return api2_source_plan(ticker=ticker, source_id=source_id)


@app.get("/api2/source-scheduler/status")
def api2_source_scheduler_status():
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", "elephant-source-scheduler.service", "--property=ActiveState,SubState,MainPID"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        systemd = {}
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                key, _, value = line.partition("=")
                if key:
                    systemd[key] = value
        else:
            systemd = {"error": result.stderr.strip() or "service not found"}
    except Exception as exc:
        systemd = {"error": str(exc)}

    plan = create_daily_plan()
    return {
        "service": "elephant-source-scheduler.service",
        "systemd": systemd,
        "planned_tasks": len(plan),
        "next_tasks": [
            {
                "source_id": t.source_id,
                "scope": t.scope,
                "ticker": t.ticker,
                "url": t.url,
                "scheduled_at": t.scheduled_at.isoformat(),
            }
            for t in plan[:20]
        ],
    }


@app.get("/api2/source-runs")
def api2_source_runs(limit: int = 100):
    return recent_runs(limit=limit)
