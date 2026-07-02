import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import elephant.secrets as _secrets

_secrets.load()

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from elephant.source.catalog import get_source, list_sources
from elephant.source.registry import SourceRegistry
from elephant.source.run_log import recent_runs
from elephant.source.scheduler import create_daily_plan
from elephant.source.scheduler_service import source_scheduler_service
from elephant.ticker_registry import normalize_ticker
from elephant.analysis.batch import run_daily_analysis
from elephant.analysis.pipeline import analyze_ticker, load_latest_score, save_analysis


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("ELEPHANT_API2_DISABLE_SCHEDULER", "").lower() not in {"1", "true", "yes"}:
        source_scheduler_service.start()
    yield
    source_scheduler_service.stop()


app = FastAPI(title="Elephant Source API v2", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SourceCheckRequest(BaseModel):
    ticker: str
    source_id: str | None = None


class AnalysisRequest(BaseModel):
    ticker: str | None = None
    limit: int | None = None
    save: bool = True


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
    return source_scheduler_service.status()


@app.post("/api2/source-scheduler/start")
def api2_source_scheduler_start():
    started = source_scheduler_service.start()
    return {"started": started, **source_scheduler_service.status()}


@app.post("/api2/source-scheduler/stop")
def api2_source_scheduler_stop():
    stopped = source_scheduler_service.stop()
    return {"stopped": stopped, **source_scheduler_service.status()}


@app.post("/api2/source-scheduler/replan")
def api2_source_scheduler_replan():
    planned = source_scheduler_service.replan()
    return {"planned": planned, **source_scheduler_service.status()}


@app.get("/api2/source-runs")
def api2_source_runs(limit: int = 100):
    return recent_runs(limit=limit)


@app.post("/api2/analysis/run")
def api2_analysis_run(req: AnalysisRequest):
    if req.ticker:
        packet, aggregate = analyze_ticker(req.ticker)
        if req.save:
            save_analysis(packet, aggregate)
        return {"packet": packet.to_dict(), "aggregate": aggregate.to_dict(), "saved": req.save}
    result = run_daily_analysis(limit=req.limit)
    return result.to_dict()


@app.get("/api2/analysis/{ticker}/latest")
def api2_analysis_latest(ticker: str):
    result = load_latest_score(ticker)
    if not result:
        raise HTTPException(status_code=404, detail="No analysis score found")
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api2:app", host="0.0.0.0", port=9765, reload=False)
