"""Build Sheqi 2024 historical flood-disease replay using real public SAR & weather.

Fetches:
  1. Real Sentinel-1A RTC backscatter arrays from Microsoft Planetary Computer
     Data API (no auth) for 4 plain sample polygons in Sheqi County, Henan
     (3 southern Panhe/Zhaohe lowland sample grids + 1 northern non-flooded
     control grid) across 5 Relative Orbit 113 passes (2024-06-22 to 2024-08-21).
  2. Real hourly meteorological reanalysis from Open-Meteo Archive API
     (2024-07-01 to 2024-09-05) cross-checked against NASA POWER daily API.
  3. Calibrated daily LWD proxy hours via `lwd_calibration.py` vs RH>=90%.
  4. Retrospective `risk_engine.py` window replay aligned with verified official
     Sheqi 2024 milestones (F050-F057).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from data_integration import parse_geojson_geometries, parse_sar_metrics_csv  # noqa: E402
from lwd_calibration import (  # noqa: E402
    build_lwd_features,
    predict_dpd_physical,
    predict_lwd_probabilities,
)
from risk_engine import FieldScenario, assess  # noqa: E402


OUT_DIR = PROJECT_DIR / "data" / "historical_replay"
STAC_SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_NPY_URL = "https://planetarycomputer.microsoft.com/api/data/v1/item/feature.npy"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
NASA_POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

SHEQI_LAT = 33.06
SHEQI_LON = 112.94
EVENT_ID = "FLOOD-2024-07-SHEQI"
METHOD_VERSION = "pc_s1_rtc_vv_lt_minus14_and_delta_le_minus2p0_v0.1"

SAMPLE_PLOTS: list[dict[str, Any]] = [
    {
        "field_id": "SHEQI_PLAIN_01",
        "role": "flooded_sample_grid",
        "zone": "社旗南部潘河—赵河下游低洼平原样本格 1",
        "bbox": [112.89, 32.85, 112.92, 32.88],
    },
    {
        "field_id": "SHEQI_PLAIN_02",
        "role": "flooded_sample_grid",
        "zone": "社旗南部潘河—赵河下游低洼平原样本格 2",
        "bbox": [112.91, 32.85, 112.94, 32.88],
    },
    {
        "field_id": "SHEQI_PLAIN_03",
        "role": "flooded_sample_grid",
        "zone": "社旗南部平原过渡样本格 3",
        "bbox": [112.89, 32.88, 112.92, 32.91],
    },
    {
        "field_id": "SHEQI_CTRL_01",
        "role": "control_sample_grid",
        "zone": "社旗北部相对高地农田对照样本格",
        "bbox": [113.02, 33.10, 113.05, 33.13],
    },
]

OFFICIAL_MILESTONES: dict[str, str] = {
    "2024-07-14": "F050 强降水开始（7/14–18 社旗累计 870.8 mm，破县纪录）",
    "2024-07-16": "Sentinel-1A 过境捕获南部低洼样本格峰值积水",
    "2024-07-28": "Sentinel-1A 重访显示样本格明水消退至 <1%",
    "2024-07-29": "公开报道：社旗县全县雨水退去（调研报告 §15.5）",
    "2024-07-30": "F057 南阳市召开玉米南方锈病防控部署会",
    "2024-08-02": "F056 截至当日社旗累计改种 14.72 万亩",
    "2024-08-27": "F053 南阳市查见玉米南方锈病（全市病株率 2.51%、病叶率 2.99%，点名社旗部分田块偏高）",
    "2024-08-29": "F054 南阳市通知将洪涝灾害区域列为南方锈病防控重点，9/5 前普防一遍",
}


def build_sample_geojson() -> bytes:
    features = []
    for item in SAMPLE_PLOTS:
        x0, y0, x1, y1 = item["bbox"]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "field_id": item["field_id"],
                    "role": item["role"],
                    "zone": item["zone"],
                    "geometry_origin": "regional_sample_grid_not_parcel_survey",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
                    ],
                },
            }
        )
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "case_id": "henan_maize_2026",
            "event_id": EVENT_ID,
            "note": "Regional plain sample grids for retrospective SAR replay; not surveyed farm boundaries.",
        },
        "features": features,
    }
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    parse_geojson_geometries(raw, case_id="henan_maize_2026", source="ftw_prediction")
    (OUT_DIR / "sheqi_2024_sample_plots.geojson").write_bytes(raw)
    return raw


def _fetch_s1_scenes() -> dict[str, str]:
    response = requests.post(
        STAC_SEARCH_URL,
        json={
            "collections": ["sentinel-1-rtc"],
            "bbox": [112.85, 32.84, 113.06, 33.14],
            "datetime": "2024-06-15T00:00:00Z/2024-08-25T23:59:59Z",
            "limit": 30,
        },
        timeout=25,
    )
    response.raise_for_status()
    features = response.json()["features"]
    by_date: dict[str, str] = {}
    for feat in features:
        dt = feat["properties"]["datetime"][:10]
        bbox = feat["bbox"]
        if bbox[1] <= 32.85 and bbox[3] >= 33.13:
            by_date[dt] = feat["id"]
    return dict(sorted(by_date.items()))


def _fetch_s1_arrays(item_id: str, bbox: list[float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x0, y0, x1, y1 = bbox
    poly = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
        },
    }
    response = requests.post(
        PC_NPY_URL,
        params={
            "collection": "sentinel-1-rtc",
            "item": item_id,
            "assets": ["vv", "vh"],
            "max_size": 512,
        },
        json=poly,
        timeout=45,
    )
    response.raise_for_status()
    arr = np.load(io.BytesIO(response.content))
    vv, vh, mask = arr[0], arr[1], arr[2]
    valid = (mask > 0) & np.isfinite(vv) & np.isfinite(vh) & (vv > 0) & (vh > 0)
    vv_db = np.where(valid, 10.0 * np.log10(np.maximum(vv, 1e-6)), np.nan)
    vh_db = np.where(valid, 10.0 * np.log10(np.maximum(vh, 1e-6)), np.nan)
    return vv_db, vh_db, valid


def build_sar_metrics() -> pd.DataFrame:
    scenes = _fetch_s1_scenes()
    if "2024-06-22" not in scenes or "2024-07-16" not in scenes:
        raise RuntimeError(f"Expected Sheqi Sentinel-1 passes missing: {scenes}")

    rows: list[dict[str, Any]] = []
    for plot in SAMPLE_PLOTS:
        field_id = plot["field_id"]
        bbox = plot["bbox"]
        arrays_by_date: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {
            dt: _fetch_s1_arrays(item_id, bbox) for dt, item_id in scenes.items()
        }
        pre_vv, _, pre_valid = arrays_by_date["2024-06-22"]
        min_h = min(arr[0].shape[0] for arr in arrays_by_date.values())
        min_w = min(arr[0].shape[1] for arr in arrays_by_date.values())
        pre_vv_c = pre_vv[:min_h, :min_w]
        pre_valid_c = pre_valid[:min_h, :min_w]

        is_control = plot["role"] == "control_sample_grid"
        for dt, item_id in scenes.items():
            vv_db, vh_db, valid = arrays_by_date[dt]
            vv_c = vv_db[:min_h, :min_w]
            vh_c = vh_db[:min_h, :min_w]
            both_valid = valid[:min_h, :min_w] & pre_valid_c
            n_valid = int(np.sum(both_valid))
            if dt == "2024-06-22":
                # Pre-flood baseline check: persistent deep water only
                flooded_mask = both_valid & (vv_c < -16.5)
                delta_med = 0.0
            else:
                delta_vv = vv_c - pre_vv_c
                flooded_mask = both_valid & (
                    ((vv_c < -14.0) & (delta_vv <= -2.0)) | (vv_c < -16.5)
                )
                delta_med = float(np.nanmedian(delta_vv[both_valid]))

            flooded_pct = round(float(np.sum(flooded_mask) / n_valid * 100.0), 2) if n_valid else 0.0
            rows.append(
                {
                    "field_id": field_id,
                    "event_id": EVENT_ID,
                    "event_date": dt,
                    "flood_start_date": "" if is_control else "2024-07-14",
                    "flood_end_date": "" if is_control else "2024-07-28",
                    "recession_date": "" if is_control else "2024-07-28",
                    "flooded_area_pct": flooded_pct,
                    "max_water_depth_m": "",
                    "source_scene_ids": item_id,
                    "method_version": METHOD_VERSION,
                    "median_vv_db": round(float(np.nanmedian(vv_c[both_valid])), 2),
                    "median_vh_db": round(float(np.nanmedian(vh_c[both_valid])), 2),
                    "delta_vv_db_vs_preflood": round(delta_med, 2),
                    "valid_pixel_count": n_valid,
                }
            )

    sar_df = pd.DataFrame(rows)
    csv_bytes = sar_df.to_csv(index=False).encode("utf-8-sig")
    parse_sar_metrics_csv(
        csv_bytes,
        case_id="henan_maize_2026",
        source="sentinel1_rtc_planetary_computer",
    )
    (OUT_DIR / "sheqi_2024_sar_flood_metrics.csv").write_bytes(csv_bytes)
    return sar_df


def build_weather_and_lwd() -> pd.DataFrame:
    om_resp = requests.get(
        OPEN_METEO_ARCHIVE_URL,
        params={
            "latitude": SHEQI_LAT,
            "longitude": SHEQI_LON,
            "start_date": "2024-07-01",
            "end_date": "2024-09-05",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "wind_speed_unit": "ms",
            "timezone": "Asia/Shanghai",
        },
        timeout=30,
    )
    om_resp.raise_for_status()
    hourly = pd.DataFrame(om_resp.json()["hourly"]).rename(
        columns={
            "time": "timestamp",
            "temperature_2m": "temperature_c",
            "relative_humidity_2m": "rh_pct",
            "precipitation": "rain_mm",
            "wind_speed_10m": "wind_speed_ms",
        }
    )
    features = build_lwd_features(hourly)
    probs, wet_flags = predict_lwd_probabilities(features)
    dpd_flags = predict_dpd_physical(features)
    hourly["rh90_wet"] = (hourly["rh_pct"] >= 90.0).astype(int)
    hourly["dpd_physical_wet"] = dpd_flags.astype(int)
    hourly["logistic_lwd_prob"] = probs
    hourly["logistic_lwd_wet"] = wet_flags.astype(int)
    hourly["date"] = pd.to_datetime(hourly["timestamp"]).dt.strftime("%Y-%m-%d")

    daily = (
        hourly.groupby("date", as_index=False)
        .agg(
            mean_temp_c=("temperature_c", "mean"),
            max_temp_c=("temperature_c", "max"),
            mean_rh_pct=("rh_pct", "mean"),
            precip_open_meteo_mm=("rain_mm", "sum"),
            mean_wind_10m_ms=("wind_speed_ms", "mean"),
            rh90_wet_hours=("rh90_wet", "sum"),
            dpd_physical_wet_hours=("dpd_physical_wet", "sum"),
            logistic_lwd_wet_hours=("logistic_lwd_wet", "sum"),
            mean_lwd_prob=("logistic_lwd_prob", "mean"),
        )
    )
    # Convert 10m wind to approx 2m agricultural spraying height (0.75 * u10)
    daily["est_wind_2m_ms"] = daily["mean_wind_10m_ms"] * 0.75

    # Cross-check against NASA POWER daily reanalysis
    np_resp = requests.get(
        NASA_POWER_DAILY_URL,
        params={
            "parameters": "T2M,RH2M,PRECTOTCORR,WS2M",
            "community": "AG",
            "longitude": SHEQI_LON,
            "latitude": SHEQI_LAT,
            "start": "20240701",
            "end": "20240905",
            "format": "JSON",
        },
        timeout=30,
    )
    np_resp.raise_for_status()
    np_params = np_resp.json()["properties"]["parameter"]
    np_dates = sorted(np_params["T2M"].keys())
    np_df = pd.DataFrame(
        {
            "date": [f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in np_dates],
            "nasa_power_temp_c": [np_params["T2M"][d] for d in np_dates],
            "nasa_power_rh_pct": [np_params["RH2M"][d] for d in np_dates],
            "nasa_power_precip_mm": [np_params["PRECTOTCORR"][d] for d in np_dates],
            "nasa_power_wind_2m_ms": [np_params["WS2M"][d] for d in np_dates],
        }
    )
    merged = daily.merge(np_df, on="date", how="left")
    for col in (
        "mean_temp_c",
        "max_temp_c",
        "mean_rh_pct",
        "precip_open_meteo_mm",
        "mean_wind_10m_ms",
        "est_wind_2m_ms",
        "mean_lwd_prob",
    ):
        merged[col] = merged[col].round(2)
    merged["source"] = "Open-Meteo ERA5/IFS Archive + NASA POWER AG cross-check"
    merged["evidence_level"] = "reanalysis_background"
    merged.to_csv(
        OUT_DIR / "sheqi_2024_weather_daily.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return merged


def build_replay_timeline(
    weather_df: pd.DataFrame,
    sar_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    flooded_peak_row = sar_df[sar_df["field_id"] == "SHEQI_PLAIN_01"].set_index("event_date")
    peak_pct_0716 = float(flooded_peak_row.loc["2024-07-16", "flooded_area_pct"])
    rec_pct_0728 = float(flooded_peak_row.loc["2024-07-28", "flooded_area_pct"])

    window_df = weather_df[weather_df["date"] >= "2024-07-14"].copy()
    replay_rows: list[dict[str, Any]] = []
    for _, wrow in window_df.iterrows():
        dt = wrow["date"]
        # Retrospective replay boundary assumptions (transparently logged)
        stage = "VT" if dt < "2024-08-01" else "R3"
        if dt < "2024-07-16":
            flood_days = float((pd.Timestamp(dt) - pd.Timestamp("2024-07-14")).days + 1)
            standing = True
            waterlog_days = 0.0
            delay_hours = 24.0 * flood_days
        elif dt < "2024-07-28":
            # SAR showed inundation on 07-16 and recession on 07-28 (12d revisit uncertainty)
            flood_days = 3.0
            standing = dt <= "2024-07-18"
            waterlog_days = float(min((pd.Timestamp(dt) - pd.Timestamp("2024-07-16")).days, 10))
            delay_hours = 72.0
        else:
            flood_days = 3.0
            standing = False
            waterlog_days = 10.0 if dt <= "2024-08-05" else 5.0
            delay_hours = 72.0

        # Before 2024-08-27 municipal survey, field diagnosis is unconfirmed
        if dt < "2024-08-27":
            symptom = "none"
            diagnosis = "not_assessed"
            pressure = "high" if dt >= "2024-07-30" else "moderate"
        else:
            symptom = "sparse"
            diagnosis = "confirmed_fungal"
            pressure = "high"

        scenario = FieldScenario(
            crop_stage=stage,
            flood_days=flood_days,
            waterlog_days=waterlog_days,
            drainage_delay_hours=delay_hours,
            standing_water=standing,
            target_disease="southern_rust",
            symptom_status=symptom,
            diagnosis_status=diagnosis,
            pre_flood_baseline="unknown",
            cultivar_name="unknown",
            disease_pressure=pressure,
            temperature_c=float(wrow["mean_temp_c"]),
            humidity_pct=float(wrow["mean_rh_pct"]),
            wind_speed_ms=float(wrow["est_wind_2m_ms"]),
            case_id="henan_maize_2026",
        )
        assessment = assess(scenario)
        win_map = {w.window: w.status for w in assessment.windows}
        replay_rows.append(
            {
                "date": dt,
                "crop_stage_assumed": stage,
                "precip_open_meteo_mm": wrow["precip_open_meteo_mm"],
                "nasa_power_precip_mm": wrow["nasa_power_precip_mm"],
                "mean_temp_c": wrow["mean_temp_c"],
                "mean_rh_pct": wrow["mean_rh_pct"],
                "rh90_wet_hours": int(wrow["rh90_wet_hours"]),
                "dpd_physical_wet_hours": int(wrow["dpd_physical_wet_hours"]),
                "logistic_lwd_wet_hours": int(wrow["logistic_lwd_wet_hours"]),
                "risk_label": assessment.risk_label,
                "environment_suitability": assessment.environment_suitability,
                "drainage_status": win_map.get("排水窗口", ""),
                "scouting_status": win_map.get("巡查窗口", ""),
                "diagnosis_status_win": win_map.get("诊断窗口", ""),
                "control_status": win_map.get("病害防治窗口", ""),
                "official_milestone": OFFICIAL_MILESTONES.get(dt, ""),
                "replay_assumption_tag": "retrospective_replay_assumption",
            }
        )

    timeline_df = pd.DataFrame(replay_rows)
    timeline_df.to_csv(
        OUT_DIR / "sheqi_2024_replay_timeline.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary = {
        "event_id": EVENT_ID,
        "location": {"county": "社旗县", "lat": SHEQI_LAT, "lon": SHEQI_LON},
        "s1_scenes_count": int(sar_df["event_date"].nunique()),
        "s1_scene_dates": sorted(sar_df["event_date"].unique().tolist()),
        "peak_flood_sample_grid_01_pct": peak_pct_0716,
        "recession_sample_grid_01_pct": rec_pct_0728,
        "control_grid_0716_pct": float(
            sar_df[(sar_df["field_id"] == "SHEQI_CTRL_01") & (sar_df["event_date"] == "2024-07-16")]["flooded_area_pct"].iloc[0]
        ),
        "open_meteo_peak_daily_precip_mm": float(weather_df["precip_open_meteo_mm"].max()),
        "open_meteo_peak_precip_date": str(
            weather_df.loc[weather_df["precip_open_meteo_mm"].idxmax(), "date"]
        ),
        "open_meteo_july14_18_total_mm": round(
            float(
                weather_df[
                    (weather_df["date"] >= "2024-07-14") & (weather_df["date"] <= "2024-07-18")
                ]["precip_open_meteo_mm"].sum()
            ),
            2,
        ),
        "nasa_power_july14_18_total_mm": round(
            float(
                weather_df[
                    (weather_df["date"] >= "2024-07-14") & (weather_df["date"] <= "2024-07-18")
                ]["nasa_power_precip_mm"].sum()
            ),
            2,
        ),
        "replay_days": int(len(timeline_df)),
        "mean_daily_rh90_hours": round(float(timeline_df["rh90_wet_hours"].mean()), 2),
        "mean_daily_dpd_physical_hours": round(
            float(timeline_df["dpd_physical_wet_hours"].mean()), 2
        ),
        "mean_daily_logistic_lwd_hours": round(
            float(timeline_df["logistic_lwd_wet_hours"].mean()), 2
        ),
        "favorable_or_optimal_days": int(
            timeline_df["environment_suitability"].isin(["optimal", "favorable"]).sum()
        ),
        "boundary": (
            "Retrospective replay uses 12-day revisit Sentinel-1A RTC sample plain grids, "
            "gridded meteorological reanalysis, and European-calibrated LWD proxy hours. "
            "It verifies pipeline coupling and timeline alignment, not parcel-level yield loss or causal infection."
        ),
    }
    (OUT_DIR / "sheqi_2024_replay_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return timeline_df, summary


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_sample_geojson()
    sar_path = OUT_DIR / "sheqi_2024_sar_flood_metrics.csv"
    if "--reuse-sar" in sys.argv and sar_path.is_file():
        sar_df = pd.read_csv(sar_path)
    else:
        sar_df = build_sar_metrics()
    weather_df = build_weather_and_lwd()
    _, summary = build_replay_timeline(weather_df, sar_df)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
