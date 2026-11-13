from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = DATA_DIR / "public_evidence_v0.1.sqlite"

SOURCE_TABLES = {
    "dataset_catalog": "public_evidence_catalog_v0.1.csv",
    "flood_ndvi_case": "public_flood_case_maize_v0.1.csv",
    "flood_case_metrics": "public_case_metrics_v0.1.csv",
    "waterlogging_survival": "public_waterlogging_survival_maize_v0.1.csv",
    "disease_progress": "public_disease_progress_maize_v0.1.csv",
}


def build_database() -> Path:
    connection = sqlite3.connect(DB_PATH)
    try:
        for table, filename in SOURCE_TABLES.items():
            frame = pd.read_csv(DATA_DIR / filename)
            frame.to_sql(table, connection, if_exists="replace", index=False)
        pd.DataFrame(
            [
                {"key": "schema_version", "value": "v0.1"},
                {"key": "source_type", "value": "bundled public evidence"},
                {"key": "write_mode", "value": "read-only at application runtime"},
            ]
        ).to_sql("metadata", connection, if_exists="replace", index=False)
        connection.execute("VACUUM")
    finally:
        connection.close()
    return DB_PATH


if __name__ == "__main__":
    print(build_database())
