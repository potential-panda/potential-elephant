import os

import duckdb
import pandas as pd

DATA_DIR = "./data"
COMMENTS_DIR = os.path.join(DATA_DIR, "dataset=yahoo_comments")
EVAL_DIR = os.path.join(DATA_DIR, "dataset=yahoo_evaluations")


def get_comments_for_analysis(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    if not ticker.endswith(".T"):
        ticker = f"{ticker}.T"
    con = duckdb.connect(database=":memory:")
    path_pattern = os.path.join(COMMENTS_DIR, f"ticker={ticker}", "date=*", "data.parquet")
    import glob

    if not glob.glob(path_pattern):
        return pd.DataFrame()
    query = f"""
    SELECT * FROM read_parquet('{path_pattern}', hive_partitioning = true)
    WHERE date BETWEEN '{start_date}' AND '{end_date}'
    ORDER BY post_datetime DESC
    """
    try:
        return con.execute(query).df()
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


def get_evaluations_for_analysis(ticker: str, start_year: str, end_year: str) -> pd.DataFrame:
    if not ticker.endswith(".T"):
        ticker = f"{ticker}.T"
    con = duckdb.connect(database=":memory:")
    path_pattern = os.path.join(EVAL_DIR, f"ticker={ticker}", "YEAR=*", "data.parquet")
    import glob

    if not glob.glob(path_pattern):
        return pd.DataFrame()
    query = f"""
    SELECT * FROM read_parquet('{path_pattern}', hive_partitioning = true)
    WHERE YEAR BETWEEN '{start_year}' AND '{end_year}'
    ORDER BY scraped_at DESC
    """
    try:
        return con.execute(query).df()
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()
