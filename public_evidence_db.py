from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


DB_PATH = Path(__file__).resolve().parent / "data" / "public_evidence_v0.1.sqlite"


def load_public_evidence(table: str) -> pd.DataFrame:
    allowed_tables = {
        "dataset_catalog",
        "flood_ndvi_case",
        "flood_case_metrics",
        "waterlogging_survival",
        "disease_progress",
    }
    if table not in allowed_tables:
        raise ValueError(f"Unknown public evidence table: {table}")
    connection = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(f'SELECT * FROM "{table}"', connection)
    finally:
        connection.close()
