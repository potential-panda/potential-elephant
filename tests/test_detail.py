import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elephant.api.detail import _sort_comments
from elephant.api.detail_v2 import _infer_source_from_loaded_data


def test_sort_comments_uses_post_datetime_descending():
    df = pd.DataFrame([
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
    ])

    sorted_df = _sort_comments(df)

    assert sorted_df.iloc[0]["post_id"] == "20"
    assert sorted_df.iloc[1]["post_id"] == "10"


def test_detail_infers_fool_source_from_loaded_news_rows():
    source = _infer_source_from_loaded_data(
        "OKLO",
        "fool_quote_news",
        [
            {
                "source": "fool_us_quote_news",
                "ticker": "OKLO",
                "quote_url": "https://www.fool.com/quote/nyse/oklo/",
                "scraped_at": "2026-07-19T16:14:00",
            }
        ],
    )

    assert source["status"] == "available"
    assert source["urls"] == ["https://www.fool.com/quote/nyse/oklo/"]
    assert source["last_row_count"] == 1
