import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elephant.api import datasets


def test_query_yahoo_comments_sorts_by_post_datetime(monkeypatch, tmp_path):
    data_dir = tmp_path
    monkeypatch.setattr(datasets, "DATA_DIR", str(data_dir))

    target = data_dir / "dataset=yahoo_comments" / "ticker=SMCI" / "date=2026-06-21"
    target.mkdir(parents=True)
    pd.DataFrame([
        {
            "post_id": "10",
            "post_datetime": "2026-06-10 09:00",
            "scraped_at": "2026-06-21 20:00",
            "body": "older post from latest scrape",
        },
        {
            "post_id": "20",
            "post_datetime": "2026-06-20 18:41",
            "scraped_at": "2026-06-21 19:00",
            "body": "newer post from earlier scrape",
        },
    ]).to_parquet(target / "data.parquet", index=False)

    rows = datasets.query_dataset("yahoo_comments", ticker="SMCI", limit=10)

    assert [row["post_id"] for row in rows] == ["20", "10"]
