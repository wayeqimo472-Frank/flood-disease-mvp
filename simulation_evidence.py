from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent / "data" / "simulation"
SUMMARY_PATH = DATA_DIR / "lizaso_maize_1991_summary.csv"
DAILY_PATH = DATA_DIR / "lizaso_maize_1991_daily.csv"
MANIFEST_PATH = DATA_DIR / "manifest.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_summary() -> pd.DataFrame:
    frame = pd.read_csv(SUMMARY_PATH)
    if frame.empty:
        raise ValueError("APSIM summary is empty")
    if set(frame["evidence_level"]) != {"simulated_validation"}:
        raise ValueError("APSIM evidence level must remain simulated_validation")
    return frame


def load_daily() -> pd.DataFrame:
    frame = pd.read_csv(DAILY_PATH, parse_dates=["date"])
    if frame.empty:
        raise ValueError("APSIM daily output is empty")
    return frame

