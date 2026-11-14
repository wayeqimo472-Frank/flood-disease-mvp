from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent / "data" / "simulation"
SUMMARY_PATH = DATA_DIR / "luohe_2021_bounded_summary.csv"
MANIFEST_PATH = DATA_DIR / "luohe_2021_bounded_manifest.json"


def load_pilot() -> pd.DataFrame:
    frame = pd.read_csv(SUMMARY_PATH)
    if frame.empty:
        raise ValueError("Luohe pilot summary is empty")
    if set(frame["direction_gate"]) != {"pass"}:
        raise ValueError("Luohe pilot must preserve its qualitative gate result")
    if set(frame["quantitative_status"]) != {
        "not_calibrated_proxy_cultivar"
    }:
        raise ValueError("Luohe proxy scenarios cannot be marked calibrated")
    return frame


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
