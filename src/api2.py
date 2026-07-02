import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import elephant.secrets as _secrets

_secrets.load()

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from elephant.source.catalog import get_source, list_sources
from elephant.source.registry import SourceRegistry
from elephant.source.run_log import recent_runs
from elephant.source.scheduler import create_daily_plan
from elephant.source.scheduler_service import source_scheduler_service
from elephant.api.tickers import get_tickers as get_tickers_v1
from elephant.api.dive import start_dive as start_dive_v1, get_job as get_dive_job_v1
from elephant.api.detail_v2 import get_detail as get_detail_v2
from elephant.api.tree import get_tree as get_tree_v1
from elephant.config import TICKERS_FILE
from elephant.ticker_registry import is_jp_ticker, load_cache, load_us_tickers
from elephant.ticker_registry import normalize_ticker
from elephant.analysis.batch import run_daily_analysis
from elephant.api import datasets
from elephant.api.prices import get_price_changes
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


class DiveRequest(BaseModel):
    ticker: str


class AnalysisRequest(BaseModel):
    ticker: str | None = None
    limit: int | None = None
    save: bool = True


@app.get("/api2/sources")
def api2_sources(scope: str | None = Query(None, pattern="^(market|ticker)$")):
    return [s.to_dict() for s in list_sources(scope=scope)]


@app.get("/api2/tickers")
def api2_tickers():
    return get_tickers_v1()


@app.get("/api2/tickers/overview")
def api2_tickers_overview():
    cache = load_cache(TICKERS_FILE)
    us_status = load_us_tickers(TICKERS_FILE)
    registry = SourceRegistry()

    rank_map: dict[str, int] = {}
    try:
        with Path(TICKERS_FILE).open(encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                ticker = line.strip()
                if ticker:
                    rank_map[ticker] = idx
    except FileNotFoundError:
        pass

    jp_tickers = set(rank_map)
    us_tickers = {t for t in (set(cache) | set(us_status)) if not is_jp_ticker(t)}

    def build_row(ticker: str) -> dict:
        entry = cache.get(ticker) or {}
        if isinstance(entry, str):
            entry = {"last_seen": entry, "speed_history": []}
        sources = registry.resolved_sources(ticker)
        return {
            "ticker": ticker,
            "market": "JP" if ticker in jp_tickers else "US",
            "bbs_rank": rank_map.get(ticker),
            "last_seen": entry.get("last_seen"),
            "last_scraped_at": entry.get("last_scraped_at"),
            "speed_history": entry.get("speed_history", []),
            "sources": sources,
            "in_tickers_us_file": ticker in us_status,
            "us_bbs": us_status.get(ticker, {}).get("bbs"),
            "us_minkabu": us_status.get(ticker, {}).get("minkabu"),
        }

    jp_items = sorted((build_row(t) for t in jp_tickers), key=lambda x: x["bbs_rank"] or 9999)
    us_items = sorted((build_row(t) for t in us_tickers), key=lambda x: x["ticker"])

    return {
        "jp_items": jp_items,
        "us_items": us_items,
        "tickers_file": TICKERS_FILE,
        "cache_file": TICKERS_FILE.replace("tickers.txt", "tickers.cache.json"),
    }


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


@app.get("/api2/detail/{ticker}")
def api2_detail(ticker: str):
    return get_detail_v2(ticker)


@app.get("/api2/tree")
def api2_tree():
    return get_tree_v1()


@app.post("/api2/dive")
def api2_dive_start(req: DiveRequest):
    job_id = start_dive_v1(req.ticker)
    return {"job_id": job_id}


@app.get("/api2/jobs/{job_id}")
def api2_job_status(job_id: str):
    result = get_dive_job_v1(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@app.get("/api2/prices")
def api2_prices(tickers: str = Query(..., description="Comma-separated ticker list")):
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    return get_price_changes(ticker_list)


@app.get("/api2/stats")
def api2_stats():
    return datasets.get_stats()


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


# --- Serve frontend ---

DIST = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.exists(DIST):
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api2:app", host="0.0.0.0", port=9765, reload=False)
