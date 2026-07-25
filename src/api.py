import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import elephant.secrets as _secrets
_secrets.load()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from elephant.api import candidates, datasets, detail, digest, dive, prices, schedule_status, tickers, atlas
from elephant import decisions as _decisions

app = FastAPI(title="Elephant Research Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Tickers ---

@app.get("/api/tickers")
def api_tickers():
    return tickers.get_tickers()


# --- Digest ---

@app.get("/api/digest/latest")
def api_digest_latest():
    result = digest.get_latest()
    if not result:
        raise HTTPException(status_code=404, detail="No digest found")
    return result


@app.get("/api/digest/list")
def api_digest_list():
    return digest.list_digests()


@app.get("/api/digest/{date}")
def api_digest_by_date(date: str):
    result = digest.get_by_date(date)
    if not result:
        raise HTTPException(status_code=404, detail="Digest not found")
    return result


@app.post("/api/digest/generate")
def api_digest_generate():
    job_id = digest.start_generate()
    return {"job_id": job_id}


# --- Schedule ---

@app.get("/api/schedule/status")
def api_schedule_status():
    return schedule_status.get_status()


@app.get("/api/schedule/plan")
def api_schedule_plan():
    return schedule_status.get_dry_run_plan()


# --- Atlas ---

@app.get("/api/atlas")
def api_atlas():
    return atlas.get_atlas()


@app.get("/api/tree")
def api_tree_alias():
    return atlas.get_atlas()


# --- Dive ---

class DiveRequest(BaseModel):
    ticker: str


@app.post("/api/dive")
def api_dive_start(req: DiveRequest):
    job_id = dive.start_dive(req.ticker)
    return {"job_id": job_id}


@app.get("/api/dive/list")
def api_dive_list():
    return dive.list_dives()


@app.get("/api/dive/{ticker}/latest")
def api_dive_latest(ticker: str):
    result = dive.get_latest(ticker)
    if not result:
        raise HTTPException(status_code=404, detail="No dive found for this ticker")
    return result


# --- Jobs (polling for async tasks) ---

@app.get("/api/jobs/{job_id}")
def api_job_status(job_id: str):
    result = digest.get_job(job_id) or dive.get_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


# --- Detail ---

@app.get("/api/detail/{ticker}")
def api_detail(ticker: str):
    return detail.get_detail(ticker)


# --- Candidates ---

@app.get("/api/candidates")
def api_candidates(
    queue: str = Query(None, description="Filter by queue: A, B, C, or suppressed"),
    include_suppressed: bool = Query(False, description="Include suppressed candidates"),
):
    return candidates.get_candidates(queue=queue, include_suppressed=include_suppressed)


# --- Prices ---

@app.get("/api/prices")
def api_prices(tickers: str = Query(..., description="Comma-separated ticker list")):
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    return prices.get_price_changes(ticker_list)


# --- Decisions ---

class DecisionRequest(BaseModel):
    ticker: str
    decision: str
    reason: str = ""
    suppress_days: int = 30  # ignored for "pass" — escalating suppression is automatic
    what_would_change: str = ""
    snapshot: dict = {}
    evidence_ids: list = []


@app.post("/api/decisions")
def api_decision_record(req: DecisionRequest):
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


@app.get("/api/decisions")
def api_decision_list():
    return _decisions.list_all()


@app.delete("/api/decisions/{ticker}")
def api_decision_remove(ticker: str):
    removed = _decisions.remove(ticker)
    return {"removed": removed, "ticker": ticker}


# --- Watchlist ---

@app.get("/api/watchlist")
def api_watchlist():
    from datetime import date as _date
    from elephant.api.prices import get_price_changes

    flagged = [d for d in _decisions.list_all() if d.get("decision") in {"value_chain_candidate", "watch"}]
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

        # Return since flag: computed from stored close vs current close
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
            "current": {
                "return_1m":  cp.get("1m"),
                "return_3m":  cp.get("3m"),
                "return_1y":  cp.get("1y"),
                "last_close": cur_close,
                "price_date": cp.get("last_date"),
            },
            "since_flag": since_flag,
        })

    return result


# --- Datasets ---

@app.get("/api/stats")
def api_stats():
    return datasets.get_stats()


@app.get("/api/query")
def api_query(
    dataset: str = Query(...),
    ticker: str = Query(None),
    keyword: str = Query(None),
    limit: int = Query(50),
):
    rows = datasets.query_dataset(dataset, ticker=ticker, keyword=keyword, limit=limit)
    return {"items": rows, "data_dir": datasets.DATA_DIR}


# --- Serve frontend ---

DIST = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.exists(DIST):
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=9765, reload=True)
