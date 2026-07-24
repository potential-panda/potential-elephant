import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

import elephant.secrets as _secrets

_secrets.load()

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from elephant import decisions as _decisions
from elephant.source.catalog import get_source, list_sources
from elephant.source.registry import SourceRegistry
from elephant.source.run_log import recent_runs
from elephant.source.scheduler import create_daily_plan
from elephant.source.scheduler_service import source_scheduler_service
from elephant.api.tickers import get_tickers as get_tickers_v1
from elephant.api.candidates import get_candidates as get_candidates_v1
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


def _parse_iso(ts: str | None):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _latest_timestamp(*values: tuple[str, str | None]) -> tuple[str | None, str | None]:
    latest_dt = None
    latest_source = None
    for source_name, ts in values:
        dt = _parse_iso(ts)
        if dt and (latest_dt is None or dt > latest_dt):
            latest_dt = dt
            latest_source = source_name
    if latest_dt is None:
        return None, None
    return latest_dt.isoformat(timespec="seconds"), latest_source


def _latest_speed(entry: dict) -> tuple[float | None, list[dict]]:
    history = entry.get("speed_history", [])
    if not isinstance(history, list):
        return None, []
    normalized = sorted(
        [h for h in history if isinstance(h, dict) and h.get("date")],
        key=lambda h: h.get("date", ""),
        reverse=True,
    )
    latest = normalized[0].get("comments_per_hour") if normalized else None
    try:
        latest_speed = float(latest) if latest is not None else None
    except Exception:
        latest_speed = None
    return latest_speed, normalized


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


class DecisionRequest(BaseModel):
    ticker: str
    decision: str
    reason: str = ""
    suppress_days: int = 30
    what_would_change: str = ""
    snapshot: dict = {}
    evidence_ids: list = []


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
        last_updated_at, last_updated_source = _latest_timestamp(
            ("cache", entry.get("last_scraped_at")),
            *(
                (f"source:{source_id}", source.get("last_harvested_at"))
                for source_id, source in sources.items()
                if isinstance(source, dict)
            ),
        )
        speed_latest, speed_history = _latest_speed(entry)
        return {
            "ticker": ticker,
            "market": "JP" if ticker in jp_tickers else "US",
            "bbs_rank": rank_map.get(ticker),
            "last_seen": entry.get("last_seen"),
            "last_scraped_at": entry.get("last_scraped_at"),
            "last_updated_at": last_updated_at,
            "last_updated_source": last_updated_source,
            "speed_latest": speed_latest,
            "speed_history": speed_history,
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


@app.get("/api2/candidates")
def api2_candidates(
    queue: str | None = Query(None, description="Filter by queue: A, B, C, or suppressed"),
    include_suppressed: bool = Query(False, description="Include suppressed candidates"),
):
    return get_candidates_v1(queue=queue, include_suppressed=include_suppressed)


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


@app.post("/api2/decisions")
def api2_decision_record(req: DecisionRequest):
    if req.decision not in _decisions.VALID_DECISIONS:
        raise HTTPException(status_code=400, detail=f"decision must be one of {sorted(_decisions.VALID_DECISIONS)}")
    entry = _decisions.record(
        ticker=req.ticker,
        decision=req.decision,
        reason=req.reason,
        suppress_days=req.suppress_days,
        what_would_change=req.what_would_change,
        snapshot=req.snapshot,
    )
    return entry


@app.get("/api2/decisions")
def api2_decision_list():
    return _decisions.list_all()


@app.delete("/api2/decisions/{ticker}")
def api2_decision_remove(ticker: str):
    removed = _decisions.remove(ticker)
    return {"removed": removed, "ticker": ticker}


@app.get("/api2/watchlist")
def api2_watchlist():
    from datetime import date as _date
    from elephant.api.prices import get_price_changes

    flagged = [d for d in _decisions.list_all() if d.get("decision") in {"river_candidate", "watch"}]
    if not flagged:
        return []

    tickers = [d["ticker"] for d in flagged]
    current = get_price_changes(tickers)

    today = _date.today()
    result = []
    for dec in flagged:
        ticker = dec["ticker"]
        snap = dec.get("snapshot", {})
        cp = current.get(ticker, {})

        days_since = None
        flagged_date = dec.get("date", "")
        if flagged_date:
            try:
                days_since = (today - _date.fromisoformat(flagged_date)).days
            except Exception:
                pass

        since_flag = None
        snap_close = snap.get("last_close")
        cur_close = cp.get("last_close")
        if snap_close and cur_close and snap_close > 0:
            since_flag = round((cur_close - snap_close) / snap_close * 100, 2)

        result.append({
            "ticker": ticker,
            "flagged_date": flagged_date,
            "days_since": days_since,
            "reason": dec.get("reason", ""),
            "snapshot": snap,
            "current": cp,
            "since_flag": since_flag,
        })
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
