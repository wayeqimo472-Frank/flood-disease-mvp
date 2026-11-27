"""Multi-feature Leaf Wetness Duration (LWD) proxy calibration and inference.

Provides physical feature extraction (dew-point depression, vapor pressure
deficit, lagged rainfall, nocturnal flag) and calibrated hourly wetness
probability estimation without adding heavy ML dependencies. All outputs are
explicitly tagged as meteorological proxy estimates, not field LWD sensor
measurements.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_LWD_MODEL_PATH = (
    PROJECT_DIR
    / "data"
    / "public_evidence_v0.2"
    / "lwd_calibration_model_v0.1.json"
)
DEFAULT_LWD_SUMMARY_PATH = (
    PROJECT_DIR
    / "data"
    / "public_evidence_v0.2"
    / "lwd_calibration_summary.csv"
)
DEFAULT_LWD_CV_PATH = (
    PROJECT_DIR
    / "data"
    / "public_evidence_v0.2"
    / "lwd_calibration_cv_metrics.csv"
)

FEATURE_COLUMNS = (
    "dew_point_depression_c",
    "is_raining",
    "rain_prev3h_mm",
    "is_night",
)
ALL_FEATURE_COLUMNS = (
    "temperature_c",
    "rh_pct",
    "dew_point_depression_c",
    "vpd_kpa",
    "rain_mm",
    "is_raining",
    "rain_prev3h_mm",
    "wind_speed_ms",
    "is_night",
)


@dataclass(frozen=True)
class LwdEstimate:
    wet_probability: float | None
    is_wet: bool | None
    dpd_physical_wet: bool | None
    dew_point_depression_c: float | None
    vpd_kpa: float | None
    model_version: str
    evidence_level: str
    boundary_note: str


def compute_dew_point_depression(
    temperature_c: pd.Series | np.ndarray | float,
    rh_pct: pd.Series | np.ndarray | float,
) -> pd.Series | np.ndarray | float:
    """Return T - T_dew (C) using the Magnus-Tetens saturation formulation."""
    a = 17.625
    b = 243.04
    if isinstance(temperature_c, (int, float)) and isinstance(rh_pct, (int, float)):
        rh_clipped = min(max(float(rh_pct), 1.0), 100.0)
        gamma = math.log(rh_clipped / 100.0) + (a * float(temperature_c)) / (
            b + float(temperature_c)
        )
        dew_point = (b * gamma) / (a - gamma)
        return float(temperature_c) - dew_point

    temp_arr = np.asarray(temperature_c, dtype=float)
    rh_arr = np.clip(np.asarray(rh_pct, dtype=float), 1.0, 100.0)
    gamma = np.log(rh_arr / 100.0) + (a * temp_arr) / (b + temp_arr)
    dew_point = (b * gamma) / (a - gamma)
    result = temp_arr - dew_point
    if isinstance(temperature_c, pd.Series):
        return pd.Series(result, index=temperature_c.index)
    return result


def compute_vpd_kpa(
    temperature_c: pd.Series | np.ndarray | float,
    rh_pct: pd.Series | np.ndarray | float,
) -> pd.Series | np.ndarray | float:
    """Return vapor pressure deficit (kPa) from temperature and relative humidity."""
    if isinstance(temperature_c, (int, float)) and isinstance(rh_pct, (int, float)):
        rh_clipped = min(max(float(rh_pct), 0.0), 100.0)
        es = 0.6108 * math.exp((17.27 * float(temperature_c)) / (float(temperature_c) + 237.3))
        return max(es * (1.0 - rh_clipped / 100.0), 0.0)

    temp_arr = np.asarray(temperature_c, dtype=float)
    rh_arr = np.clip(np.asarray(rh_pct, dtype=float), 0.0, 100.0)
    es = 0.6108 * np.exp((17.27 * temp_arr) / (temp_arr + 237.3))
    result = np.maximum(es * (1.0 - rh_arr / 100.0), 0.0)
    if isinstance(temperature_c, pd.Series):
        return pd.Series(result, index=temperature_c.index)
    return result


def build_lwd_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build harmonized hourly LWD calibration features from meteorological columns."""
    out = pd.DataFrame(index=frame.index)
    temp = pd.to_numeric(frame["temperature_c"], errors="coerce")
    rh = pd.to_numeric(frame["rh_pct"], errors="coerce").clip(0.0, 100.0)
    rain = pd.to_numeric(frame["rain_mm"], errors="coerce").fillna(0.0).clip(lower=0.0)
    wind = pd.to_numeric(frame["wind_speed_ms"], errors="coerce").clip(lower=0.0)

    timestamps = pd.to_datetime(frame["timestamp"], errors="coerce")
    hours = timestamps.dt.hour
    is_night = ((hours >= 20) | (hours <= 6)).astype(float)
    is_night = is_night.where(hours.notna(), np.nan)

    out["temperature_c"] = temp
    out["rh_pct"] = rh
    out["dew_point_depression_c"] = compute_dew_point_depression(temp, rh)
    out["vpd_kpa"] = compute_vpd_kpa(temp, rh)
    out["rain_mm"] = rain
    out["is_raining"] = (rain > 0.0).astype(float)
    out["rain_prev3h_mm"] = rain.rolling(window=3, min_periods=1).sum()
    out["wind_speed_ms"] = wind
    out["is_night"] = is_night
    return out


@lru_cache(maxsize=4)
def load_lwd_model(model_path: Path | str = DEFAULT_LWD_MODEL_PATH) -> dict[str, Any]:
    path = Path(model_path)
    return json.loads(path.read_text(encoding="utf-8"))


def _sigmoid(z: np.ndarray | float) -> np.ndarray | float:
    clipped = np.clip(z, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def predict_lwd_probabilities(
    features: pd.DataFrame,
    *,
    model: dict[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Predict hourly wetness probabilities and boolean flags for a feature frame."""
    loaded = model or load_lwd_model()
    cols = loaded["feature_names"]
    means = np.array([loaded["scaler_mean"][c] for c in cols], dtype=float)
    stds = np.array([loaded["scaler_std"][c] for c in cols], dtype=float)
    weights = np.array([loaded["weights"][c] for c in cols], dtype=float)
    bias = float(loaded["intercept"])
    threshold = float(loaded["probability_threshold"])

    x = features[cols].to_numpy(dtype=float)
    # Only impute optional secondary features using training means; core T/RH must be present
    core_missing = features["temperature_c"].isna() | features["rh_pct"].isna()
    for col_idx in range(x.shape[1]):
        col_missing = np.isnan(x[:, col_idx])
        if col_missing.any():
            x[col_missing, col_idx] = means[col_idx]

    z = ((x - means) / stds) @ weights + bias
    probs = _sigmoid(z)
    probs = np.where(core_missing.to_numpy(), np.nan, probs)
    flags = probs >= threshold
    return probs, flags


def predict_dpd_physical(
    features: pd.DataFrame,
    *,
    dpd_threshold_c: float | None = None,
    model: dict[str, Any] | None = None,
) -> np.ndarray:
    """Predict hourly canopy wetness using physical DPD threshold OR rainfall."""
    loaded = model or load_lwd_model()
    threshold = float(
        dpd_threshold_c
        if dpd_threshold_c is not None
        else loaded.get("dpd_threshold_c", 2.75)
    )
    dpd = features["dew_point_depression_c"].to_numpy(dtype=float)
    rain = features["rain_mm"].fillna(0.0).to_numpy(dtype=float)
    core_missing = features["temperature_c"].isna() | features["rh_pct"].isna()
    flags = (dpd <= threshold) | (rain > 0.0)
    return np.where(core_missing.to_numpy(), False, flags)


def estimate_lwd_hour_probability(
    temperature_c: float | None,
    rh_pct: float | None,
    *,
    rain_mm: float | None = None,
    wind_speed_ms: float | None = None,
    is_night: float | None = None,
    rain_prev3h_mm: float | None = None,
    model_path: Path | str = DEFAULT_LWD_MODEL_PATH,
) -> LwdEstimate:
    """Estimate single-hour canopy wetness probability with explicit data-gap guard."""
    loaded = load_lwd_model(model_path)
    boundary = (
        "气象代理估算（proxy_model_estimate），基于欧洲实测站点校准；"
        "不能替代田间冠层LWD实测。"
    )
    if temperature_c is None or rh_pct is None or (
        isinstance(temperature_c, float) and math.isnan(temperature_c)
    ) or (isinstance(rh_pct, float) and math.isnan(rh_pct)):
        return LwdEstimate(
            wet_probability=None,
            is_wet=None,
            dpd_physical_wet=None,
            dew_point_depression_c=None,
            vpd_kpa=None,
            model_version=loaded["model_version"],
            evidence_level="proxy_model_estimate",
            boundary_note=boundary,
        )

    dpd = float(compute_dew_point_depression(float(temperature_c), float(rh_pct)))
    vpd = float(compute_vpd_kpa(float(temperature_c), float(rh_pct)))
    means = loaded["scaler_mean"]
    stds = loaded["scaler_std"]
    weights = loaded["weights"]

    rain_val = float(rain_mm) if rain_mm is not None else float(means.get("rain_mm", 0.0))
    is_rain_val = float(rain_val > 0.0) if rain_mm is not None else float(means["is_raining"])
    row = {
        "temperature_c": float(temperature_c),
        "rh_pct": float(min(max(rh_pct, 0.0), 100.0)),
        "dew_point_depression_c": dpd,
        "vpd_kpa": vpd,
        "rain_mm": rain_val,
        "is_raining": is_rain_val,
        "rain_prev3h_mm": (
            float(rain_prev3h_mm)
            if rain_prev3h_mm is not None
            else (rain_val if rain_mm is not None else float(means["rain_prev3h_mm"]))
        ),
        "wind_speed_ms": (
            float(wind_speed_ms)
            if wind_speed_ms is not None
            else float(means.get("wind_speed_ms", 0.0))
        ),
        "is_night": float(is_night) if is_night is not None else float(means["is_night"]),
    }

    z = float(loaded["intercept"])
    for name in loaded["feature_names"]:
        z += ((row[name] - float(means[name])) / float(stds[name])) * float(weights[name])
    prob = float(_sigmoid(z))
    threshold = float(loaded["probability_threshold"])
    dpd_thresh = float(loaded.get("dpd_threshold_c", 2.75))
    dpd_wet = bool(dpd <= dpd_thresh or (rain_mm is not None and float(rain_mm) > 0.0))
    return LwdEstimate(
        wet_probability=round(prob, 4),
        is_wet=bool(prob >= threshold),
        dpd_physical_wet=dpd_wet,
        dew_point_depression_c=round(dpd, 3),
        vpd_kpa=round(vpd, 4),
        model_version=loaded["model_version"],
        evidence_level="proxy_model_estimate",
        boundary_note=boundary,
    )
