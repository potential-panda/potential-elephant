import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import elephant.secrets as _secrets
_secrets.load()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from elephant.api import candidates, datasets, detail, digest, dive, prices, schedule_status, tickers, tree

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


# --- Tree ---

@app.get("/api/tree")
def api_tree():
    return tree.get_tree()


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
def api_candidates(queue: str = Query(None, description="Filter by queue: A, B, or C")):
    return candidates.get_candidates(queue=queue)


# --- Prices ---

@app.get("/api/prices")
def api_prices(tickers: str = Query(..., description="Comma-separated ticker list")):
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    return prices.get_price_changes(ticker_list)


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
