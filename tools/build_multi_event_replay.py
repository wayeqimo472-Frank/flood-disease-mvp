"""Build multi-event historical flood-disease replays (Xunxian 2021 + Zhuozhou 2023)
and compile a unified 3-event comparison summary alongside Sheqi 2024.

Uses:
  1. Microsoft Planetary Computer Sentinel-1A RTC (no auth) with parallel
     spatial cutouts (`feature.npy`).
  2. Open-Meteo Archive hourly weather cross-checked against NASA POWER daily.
  3. Gleason physical baseline, DPD physical threshold, and calibrated logistic
     LWD proxy hours via `lwd_calibration.py`.
  4. Retrospective `risk_engine.assess()` timeline aligned with verified official
     milestones from `调研报告_v1.3.md`.
"""

from __future__ import annotations

import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
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
    predict_gleason_physical,
    predict_lwd_probabilities,
)
from risk_engine import FieldScenario, assess  # noqa: E402


OUT_DIR = PROJECT_DIR / "data" / "historical_replay"
STAC_SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_NPY_URL = "https://planetarycomputer.microsoft.com/api/data/v1/item/feature.npy"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
NASA_POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
METHOD_VERSION = "pc_s1_rtc_vv_lt_minus14_and_delta_le_minus2p0_v0.1"


@dataclass(frozen=True)
class EventSpec:
    slug: str
    event_id: str
    county_label: str
    flood_type: str
    lat: float
    lon: float
    search_bbox: list[float]
    stac_datetime: str
    baseline_date: str
    relative_orbit: int
    weather_start: str
    weather_end: str
    replay_start: str
    replay_end: str
    flood_start_date: str
    flood_end_date: str
    recession_date: str
    official_precip_note: str
    sample_plots: list[dict[str, Any]]
    milestones: dict[str, str]


XUNXIAN_SPEC = EventSpec(
    slug="xunxian_2021",
    event_id="FLOOD-2021-07-XUNXIAN",
    county_label="鹤壁浚县",
    flood_type="蓄滞洪区长历时深水（≥3个月）",
    lat=35.67,
    lon=114.55,
    search_bbox=[114.40, 35.48, 114.68, 35.80],
    stac_datetime="2021-07-01T00:00:00Z/2021-10-25T23:59:59Z",
    baseline_date="2021-07-15",
    relative_orbit=40,
    weather_start="2021-07-10",
    weather_end="2021-10-20",
    replay_start="2021-07-18",
    replay_end="2021-09-25",
    flood_start_date="2021-07-20",
    flood_end_date="2021-08-24",
    recession_date="2021-11-04",
    official_precip_note="7·20 极端暴雨+蓄滞洪区行蓄洪（小河镇 62 村 10.81 万亩受淹，蓄滞洪区 11-04 基本退水）",
    sample_plots=[
        {
            "field_id": "XUNXIAN_XIAOHE_S",
            "role": "flooded_sample_grid",
            "zone": "浚县小河镇南部蓄滞洪区农田样本格",
            "bbox": [114.42, 35.50, 114.48, 35.56],
        },
        {
            "field_id": "XUNXIAN_XIAOHE_N",
            "role": "flooded_sample_grid",
            "zone": "浚县小河镇北部蓄滞洪区农田样本格",
            "bbox": [114.42, 35.56, 114.48, 35.62],
        },
        {
            "field_id": "XUNXIAN_BAISIPO_W",
            "role": "flooded_sample_grid",
            "zone": "浚县白寺坡西蓄滞洪区农田样本格",
            "bbox": [114.48, 35.56, 114.54, 35.62],
        },
        {
            "field_id": "XUNXIAN_CTRL_NE",
            "role": "control_sample_grid",
            "zone": "浚县东北部未受淹高地农田对照样本格",
            "bbox": [114.60, 35.72, 114.66, 35.78],
        },
    ],
    milestones={
        "2021-07-20": "河南 7·20 特大暴雨过程启动",
        "2021-07-23": "省级发布会：全省农田积水 1132 万亩，玉米受灾 746 万亩",
        "2021-07-27": "Sentinel-1A 过境捕获小河镇/白寺坡蓄滞洪区峰值淹没（>30%）",
        "2021-08-03": "省级灾后发布会：全省受灾 1470 万亩、绝收 570 万亩",
        "2021-08-20": "Sentinel-1A 显示滞水满月后小河/白寺坡仍存 8%–11% 积水",
        "2021-08-24": "F041 鹤壁发布会：小河镇 62 村 10.81 万亩受淹，61/62 村退水",
        "2021-09-13": "Sentinel-1A 监测局部低洼滞水仍缓退（11-04 蓄滞洪区全面退水）",
    },
)

ZHUOZHOU_SPEC = EventSpec(
    slug="zhuozhou_2023",
    event_id="FLOOD-2023-07-ZHUOZHOU",
    county_label="保定涿州",
    flood_type="蓄滞洪区＋超标准行洪",
    lat=39.48,
    lon=115.97,
    search_bbox=[115.80, 39.22, 116.12, 39.62],
    stac_datetime="2023-07-10T00:00:00Z/2023-09-05T23:59:59Z",
    baseline_date="2023-07-24",
    relative_orbit=142,
    weather_start="2023-07-20",
    weather_end="2023-09-05",
    replay_start="2023-07-29",
    replay_end="2023-09-05",
    flood_start_date="2023-07-29",
    flood_end_date="2023-08-09",
    recession_date="2023-08-09",
    official_precip_note="F046 7-29 至 8-2 过程平均雨量 358.7 mm、最大 442.2 mm；张坊站洪峰 6200 m³/s",
    sample_plots=[
        {
            "field_id": "ZHUOZHOU_LANGOUWA_SW",
            "role": "flooded_sample_grid",
            "zone": "涿州兰沟洼蓄滞洪区西南农田样本格",
            "bbox": [116.00, 39.24, 116.04, 39.28],
        },
        {
            "field_id": "ZHUOZHOU_LANGOUWA_SE",
            "role": "flooded_sample_grid",
            "zone": "涿州兰沟洼蓄滞洪区东南农田样本格",
            "bbox": [116.04, 39.24, 116.08, 39.28],
        },
        {
            "field_id": "ZHUOZHOU_LANGOUWA_NW",
            "role": "flooded_sample_grid",
            "zone": "涿州兰沟洼蓄滞洪区西北农田样本格",
            "bbox": [116.00, 39.28, 116.04, 39.32],
        },
        {
            "field_id": "ZHUOZHOU_CTRL_NW",
            "role": "control_sample_grid",
            "zone": "涿州西北部高地农田对照样本格",
            "bbox": [115.82, 39.54, 115.88, 39.60],
        },
    ],
    milestones={
        "2023-07-29": "F046 强降雨启动（7-29 至 8-2 平均 358.7 mm）",
        "2023-08-05": "Sentinel-1A 过境捕获兰沟洼蓄滞洪区行洪峰值淹没",
        "2023-08-09": "F047 官方通报：农作物受灾 28,621 公顷，8-09 全部退水",
        "2023-08-17": "Sentinel-1A 重访确认兰沟洼明水消退至 <2%",
        "2023-08-25": "F048 投入 300 万元+50 架无人机完成 16/20 万亩飞防（预防南方锈病）",
        "2023-08-31": "F048 计划完成全部 20 万亩存活玉米统防统治",
    },
)


def _write_geojson(spec: EventSpec) -> None:
    features = []
    for item in spec.sample_plots:
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
                    "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
                },
            }
        )
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "case_id": "henan_maize_2026",
            "event_id": spec.event_id,
            "note": f"Regional sample grids for {spec.county_label} retrospective SAR replay; not parcel surveys.",
        },
        "features": features,
    }
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    parse_geojson_geometries(raw, case_id="henan_maize_2026", source="ftw_prediction")
    (OUT_DIR / f"{spec.slug}_sample_plots.geojson").write_bytes(raw)


def _fetch_scenes(spec: EventSpec) -> dict[str, str]:
    resp = requests.post(
        STAC_SEARCH_URL,
        json={
            "collections": ["sentinel-1-rtc"],
            "bbox": spec.search_bbox,
            "datetime": spec.stac_datetime,
            "limit": 40,
        },
        timeout=30,
    )
    resp.raise_for_status()
    by_date: dict[str, str] = {}
    x_min, y_min, x_max, y_max = spec.search_bbox
    for feat in resp.json()["features"]:
        props = feat["properties"]
        if props.get("sat:relative_orbit") != spec.relative_orbit:
            continue
        bbox = feat["bbox"]
        if bbox[0] <= x_min and bbox[1] <= y_min and bbox[2] >= x_max and bbox[3] >= y_max:
            by_date[props["datetime"][:10]] = feat["id"]
    return dict(sorted(by_date.items()))


def _fetch_one_cutout(args: tuple[str, str, list[float]]) -> tuple[str, str, np.ndarray, np.ndarray, np.ndarray]:
    dt, item_id, bbox = args
    x0, y0, x1, y1 = bbox
    poly = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]},
    }
    resp = requests.post(
        PC_NPY_URL,
        params={
            "collection": "sentinel-1-rtc",
            "item": item_id,
            "assets": ["vv", "vh"],
            "max_size": 384,
        },
        json=poly,
        timeout=45,
    )
    resp.raise_for_status()
    arr = np.load(io.BytesIO(resp.content))
    vv, vh, mask = arr[0], arr[1], arr[2]
    valid = (mask > 0) & np.isfinite(vv) & np.isfinite(vh) & (vv > 0) & (vh > 0)
    vv_db = np.where(valid, 10.0 * np.log10(np.maximum(vv, 1e-6)), np.nan)
    vh_db = np.where(valid, 10.0 * np.log10(np.maximum(vh, 1e-6)), np.nan)
    return dt, item_id, vv_db, vh_db, valid


def _build_sar(spec: EventSpec) -> pd.DataFrame:
    scenes = _fetch_scenes(spec)
    if spec.baseline_date not in scenes:
        raise RuntimeError(f"{spec.slug}: baseline date {spec.baseline_date} missing in {scenes}")

    rows: list[dict[str, Any]] = []
    for plot in spec.sample_plots:
        tasks = [(dt, item_id, plot["bbox"]) for dt, item_id in scenes.items()]
        with ThreadPoolExecutor(max_workers=5) as ex:
            results = list(ex.map(_fetch_one_cutout, tasks))
        arrays_by_date = {dt: (item_id, vv, vh, valid) for dt, item_id, vv, vh, valid in results}
        _, pre_vv, _, pre_valid = arrays_by_date[spec.baseline_date]
        min_h = min(arr[1].shape[0] for arr in arrays_by_date.values())
        min_w = min(arr[1].shape[1] for arr in arrays_by_date.values())
        pre_vv_c = pre_vv[:min_h, :min_w]
        pre_valid_c = pre_valid[:min_h, :min_w]
        is_control = plot["role"] == "control_sample_grid"

        for dt in sorted(arrays_by_date):
            item_id, vv_db, vh_db, valid = arrays_by_date[dt]
            vv_c = vv_db[:min_h, :min_w]
            vh_c = vh_db[:min_h, :min_w]
            both_valid = valid[:min_h, :min_w] & pre_valid_c
            n_valid = int(np.sum(both_valid))
            if dt <= spec.baseline_date:
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
                    "field_id": plot["field_id"],
                    "event_id": spec.event_id,
                    "event_date": dt,
                    "flood_start_date": "" if is_control else spec.flood_start_date,
                    "flood_end_date": "" if is_control else spec.flood_end_date,
                    "recession_date": "" if is_control else spec.recession_date,
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
    (OUT_DIR / f"{spec.slug}_sar_flood_metrics.csv").write_bytes(csv_bytes)
    return sar_df


def _build_weather(spec: EventSpec) -> pd.DataFrame:
    om_resp = requests.get(
        OPEN_METEO_ARCHIVE_URL,
        params={
            "latitude": spec.lat,
            "longitude": spec.lon,
            "start_date": spec.weather_start,
            "end_date": spec.weather_end,
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
    gleason_flags = predict_gleason_physical(features)

    hourly["rh90_wet"] = (hourly["rh_pct"] >= 90.0).astype(int)
    hourly["gleason_wet"] = gleason_flags.astype(int)
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
            gleason_wet_hours=("gleason_wet", "sum"),
            dpd_physical_wet_hours=("dpd_physical_wet", "sum"),
            logistic_lwd_wet_hours=("logistic_lwd_wet", "sum"),
            mean_lwd_prob=("logistic_lwd_prob", "mean"),
        )
    )
    daily["est_wind_2m_ms"] = daily["mean_wind_10m_ms"] * 0.75

    np_resp = requests.get(
        NASA_POWER_DAILY_URL,
        params={
            "parameters": "T2M,RH2M,PRECTOTCORR,WS2M",
            "community": "AG",
            "longitude": spec.lon,
            "latitude": spec.lat,
            "start": spec.weather_start.replace("-", ""),
            "end": spec.weather_end.replace("-", ""),
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
        OUT_DIR / f"{spec.slug}_weather_daily.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return merged


def _build_xunxian_timeline(weather_df: pd.DataFrame, sar_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    sub = weather_df[(weather_df["date"] >= XUNXIAN_SPEC.replay_start) & (weather_df["date"] <= XUNXIAN_SPEC.replay_end)]
    rows: list[dict[str, Any]] = []
    for _, wrow in sub.iterrows():
        dt = wrow["date"]
        days_since_flood = (pd.Timestamp(dt) - pd.Timestamp("2021-07-20")).days + 1
        stage = "VT" if dt < "2021-08-05" else "R3"
        if dt <= "2021-08-24":
            flood_days = float(min(max(days_since_flood, 1), 30))
            standing = True
            waterlog_days = 0.0
            delay_hours = float(min(flood_days * 24.0, 720.0))
        else:
            # Long-duration detention basin residual saturation / slow recession branch
            flood_days = 30.0
            standing = dt <= "2021-09-13"
            waterlog_days = float(min((pd.Timestamp(dt) - pd.Timestamp("2021-08-24")).days, 20))
            delay_hours = 720.0

        scenario = FieldScenario(
            crop_stage=stage,
            flood_days=flood_days,
            waterlog_days=waterlog_days,
            drainage_delay_hours=delay_hours,
            standing_water=standing,
            target_disease="stem_rot",
            symptom_status="none",
            diagnosis_status="not_assessed",
            pre_flood_baseline="unknown",
            cultivar_name="unknown",
            disease_pressure="unknown",
            temperature_c=float(wrow["mean_temp_c"]),
            humidity_pct=float(wrow["mean_rh_pct"]),
            wind_speed_ms=float(wrow["est_wind_2m_ms"]),
            case_id="henan_maize_2026",
        )
        assessment = assess(scenario)
        win_map = {w.window: w.status for w in assessment.windows}
        rows.append(
            {
                "date": dt,
                "crop_stage_assumed": stage,
                "precip_open_meteo_mm": wrow["precip_open_meteo_mm"],
                "nasa_power_precip_mm": wrow["nasa_power_precip_mm"],
                "mean_temp_c": wrow["mean_temp_c"],
                "mean_rh_pct": wrow["mean_rh_pct"],
                "rh90_wet_hours": int(wrow["rh90_wet_hours"]),
                "gleason_wet_hours": int(wrow["gleason_wet_hours"]),
                "dpd_physical_wet_hours": int(wrow["dpd_physical_wet_hours"]),
                "logistic_lwd_wet_hours": int(wrow["logistic_lwd_wet_hours"]),
                "risk_label": assessment.risk_label,
                "environment_suitability": assessment.environment_suitability,
                "drainage_status": win_map.get("排水窗口", ""),
                "scouting_status": win_map.get("巡查窗口", ""),
                "diagnosis_status_win": win_map.get("诊断窗口", ""),
                "control_status": win_map.get("病害防治窗口", ""),
                "official_milestone": XUNXIAN_SPEC.milestones.get(dt, ""),
                "replay_assumption_tag": "retrospective_detention_stem_rot_branch_capped_30d",
            }
        )

    tdf = pd.DataFrame(rows)
    tdf.to_csv(OUT_DIR / "xunxian_2021_replay_timeline.csv", index=False, encoding="utf-8-sig")

    xiaohe_s = sar_df[sar_df["field_id"] == "XUNXIAN_XIAOHE_S"].set_index("event_date")
    ctrl = sar_df[sar_df["field_id"] == "XUNXIAN_CTRL_NE"].set_index("event_date")
    storm_df = weather_df[(weather_df["date"] >= "2021-07-18") & (weather_df["date"] <= "2021-07-23")]
    summary = {
        "slug": XUNXIAN_SPEC.slug,
        "event_id": XUNXIAN_SPEC.event_id,
        "county_label": XUNXIAN_SPEC.county_label,
        "flood_type": XUNXIAN_SPEC.flood_type,
        "s1_scenes_count": int(sar_df["event_date"].nunique()),
        "s1_scene_dates": sorted(sar_df["event_date"].unique().tolist()),
        "peak_sample_field": "XUNXIAN_XIAOHE_S",
        "peak_date": "2021-07-27",
        "peak_flooded_pct": float(xiaohe_s.loc["2021-07-27", "flooded_area_pct"]),
        "followup_date": "2021-08-20",
        "followup_flooded_pct": float(xiaohe_s.loc["2021-08-20", "flooded_area_pct"]),
        "control_peak_pct": float(ctrl.loc["2021-07-27", "flooded_area_pct"]),
        "open_meteo_storm_total_mm": round(float(storm_df["precip_open_meteo_mm"].sum()), 2),
        "nasa_power_storm_total_mm": round(float(storm_df["nasa_power_precip_mm"].sum()), 2),
        "official_precip_note": XUNXIAN_SPEC.official_precip_note,
        "replay_days": int(len(tdf)),
        "mean_daily_rh90_hours": round(float(tdf["rh90_wet_hours"].mean()), 2),
        "mean_daily_gleason_hours": round(float(tdf["gleason_wet_hours"].mean()), 2),
        "mean_daily_dpd_physical_hours": round(float(tdf["dpd_physical_wet_hours"].mean()), 2),
        "mean_daily_logistic_lwd_hours": round(float(tdf["logistic_lwd_wet_hours"].mean()), 2),
        "dominant_risk_label": str(tdf["risk_label"].mode().iloc[0]),
        "boundary": "Detention basin branch maps prolonged >30d inundation to stem_rot monitoring/diagnosis only; S1 12-day revisit does not measure water depth.",
    }
    (OUT_DIR / "xunxian_2021_replay_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return tdf, summary


def _build_zhuozhou_timeline(weather_df: pd.DataFrame, sar_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    sub = weather_df[(weather_df["date"] >= ZHUOZHOU_SPEC.replay_start) & (weather_df["date"] <= ZHUOZHOU_SPEC.replay_end)]
    rows: list[dict[str, Any]] = []
    for _, wrow in sub.iterrows():
        dt = wrow["date"]
        stage = "VT" if dt < "2023-08-12" else "R3"
        if dt <= "2023-08-05":
            flood_days = float(min((pd.Timestamp(dt) - pd.Timestamp("2023-07-29")).days + 1, 7))
            standing = True
            waterlog_days = 0.0
            delay_hours = float(flood_days * 24.0)
        elif dt <= "2023-08-09":
            flood_days = 5.0
            standing = dt < "2023-08-09"
            waterlog_days = float((pd.Timestamp(dt) - pd.Timestamp("2023-08-05")).days)
            delay_hours = 96.0
        else:
            flood_days = 5.0
            standing = False
            waterlog_days = 6.0 if dt <= "2023-08-20" else 3.0
            delay_hours = 96.0

        pressure = "high" if dt >= "2023-08-17" else "moderate"
        scenario = FieldScenario(
            crop_stage=stage,
            flood_days=flood_days,
            waterlog_days=waterlog_days,
            drainage_delay_hours=delay_hours,
            standing_water=standing,
            target_disease="southern_rust",
            symptom_status="none",
            diagnosis_status="not_assessed",
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
        rows.append(
            {
                "date": dt,
                "crop_stage_assumed": stage,
                "precip_open_meteo_mm": wrow["precip_open_meteo_mm"],
                "nasa_power_precip_mm": wrow["nasa_power_precip_mm"],
                "mean_temp_c": wrow["mean_temp_c"],
                "mean_rh_pct": wrow["mean_rh_pct"],
                "rh90_wet_hours": int(wrow["rh90_wet_hours"]),
                "gleason_wet_hours": int(wrow["gleason_wet_hours"]),
                "dpd_physical_wet_hours": int(wrow["dpd_physical_wet_hours"]),
                "logistic_lwd_wet_hours": int(wrow["logistic_lwd_wet_hours"]),
                "risk_label": assessment.risk_label,
                "environment_suitability": assessment.environment_suitability,
                "drainage_status": win_map.get("排水窗口", ""),
                "scouting_status": win_map.get("巡查窗口", ""),
                "diagnosis_status_win": win_map.get("诊断窗口", ""),
                "control_status": win_map.get("病害防治窗口", ""),
                "official_milestone": ZHUOZHOU_SPEC.milestones.get(dt, ""),
                "replay_assumption_tag": "retrospective_flash_diversion_preventive_rust_unknown_occurrence",
            }
        )

    tdf = pd.DataFrame(rows)
    tdf.to_csv(OUT_DIR / "zhuozhou_2023_replay_timeline.csv", index=False, encoding="utf-8-sig")

    langouwa = sar_df[sar_df["field_id"] == "ZHUOZHOU_LANGOUWA_SW"].set_index("event_date")
    best_grid = (
        sar_df[sar_df["event_date"] == "2023-08-05"]
        .sort_values("flooded_area_pct", ascending=False)
        .iloc[0]
    )
    best_id = str(best_grid["field_id"])
    best_series = sar_df[sar_df["field_id"] == best_id].set_index("event_date")
    ctrl = sar_df[sar_df["field_id"] == "ZHUOZHOU_CTRL_NW"].set_index("event_date")
    storm_df = weather_df[(weather_df["date"] >= "2023-07-29") & (weather_df["date"] <= "2023-08-02")]
    summary = {
        "slug": ZHUOZHOU_SPEC.slug,
        "event_id": ZHUOZHOU_SPEC.event_id,
        "county_label": ZHUOZHOU_SPEC.county_label,
        "flood_type": ZHUOZHOU_SPEC.flood_type,
        "s1_scenes_count": int(sar_df["event_date"].nunique()),
        "s1_scene_dates": sorted(sar_df["event_date"].unique().tolist()),
        "peak_sample_field": best_id,
        "peak_date": "2023-08-05",
        "peak_flooded_pct": float(best_series.loc["2023-08-05", "flooded_area_pct"]),
        "followup_date": "2023-08-17",
        "followup_flooded_pct": float(best_series.loc["2023-08-17", "flooded_area_pct"]),
        "control_peak_pct": float(ctrl.loc["2023-08-05", "flooded_area_pct"]),
        "open_meteo_storm_total_mm": round(float(storm_df["precip_open_meteo_mm"].sum()), 2),
        "nasa_power_storm_total_mm": round(float(storm_df["nasa_power_precip_mm"].sum()), 2),
        "official_precip_note": ZHUOZHOU_SPEC.official_precip_note,
        "replay_days": int(len(tdf)),
        "mean_daily_rh90_hours": round(float(tdf["rh90_wet_hours"].mean()), 2),
        "mean_daily_gleason_hours": round(float(tdf["gleason_wet_hours"].mean()), 2),
        "mean_daily_dpd_physical_hours": round(float(tdf["dpd_physical_wet_hours"].mean()), 2),
        "mean_daily_logistic_lwd_hours": round(float(tdf["logistic_lwd_wet_hours"].mean()), 2),
        "dominant_risk_label": str(tdf["risk_label"].mode().iloc[0]),
        "boundary": "Zhuozhou F048 documents preventive UAV rust spraying without confirmed disease incidence; replay keeps diagnosis_status=not_assessed.",
    }
    (OUT_DIR / "zhuozhou_2023_replay_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return tdf, summary


def build_three_event_comparison(
    xunxian_summary: dict[str, Any],
    zhuozhou_summary: dict[str, Any],
) -> pd.DataFrame:
    sheqi_raw = json.loads((OUT_DIR / "sheqi_2024_replay_summary.json").read_text(encoding="utf-8"))
    sheqi_timeline = pd.read_csv(OUT_DIR / "sheqi_2024_replay_timeline.csv")
    rows = [
        {
            "event_id": sheqi_raw["event_id"],
            "county": "南阳社旗 (2024)",
            "flood_type": "平原内涝",
            "s1_scenes_count": sheqi_raw["s1_scenes_count"],
            "peak_sample_grid": "SHEQI_PLAIN_01",
            "peak_date": "2024-07-16",
            "peak_flooded_pct": sheqi_raw["peak_flood_sample_grid_01_pct"],
            "followup_date": "2024-07-28",
            "followup_flooded_pct": sheqi_raw["recession_sample_grid_01_pct"],
            "control_peak_pct": sheqi_raw["control_grid_0716_pct"],
            "reanalysis_storm_open_meteo_mm": sheqi_raw["open_meteo_july14_18_total_mm"],
            "reanalysis_storm_nasa_power_mm": sheqi_raw["nasa_power_july14_18_total_mm"],
            "official_storm_context": "7-14 至 18 累计 870.8 mm（破县纪录），8-27 市局确认南方锈病点名社旗",
            "mean_daily_rh90_hours": sheqi_raw["mean_daily_rh90_hours"],
            "mean_daily_dpd_physical_hours": sheqi_raw["mean_daily_dpd_physical_hours"],
            "dominant_risk_label": str(sheqi_timeline["risk_label"].mode().iloc[0]),
        },
        {
            "event_id": xunxian_summary["event_id"],
            "county": "鹤壁浚县 (2021)",
            "flood_type": xunxian_summary["flood_type"],
            "s1_scenes_count": xunxian_summary["s1_scenes_count"],
            "peak_sample_grid": xunxian_summary["peak_sample_field"],
            "peak_date": xunxian_summary["peak_date"],
            "peak_flooded_pct": xunxian_summary["peak_flooded_pct"],
            "followup_date": xunxian_summary["followup_date"],
            "followup_flooded_pct": xunxian_summary["followup_flooded_pct"],
            "control_peak_pct": xunxian_summary["control_peak_pct"],
            "reanalysis_storm_open_meteo_mm": xunxian_summary["open_meteo_storm_total_mm"],
            "reanalysis_storm_nasa_power_mm": xunxian_summary["nasa_power_storm_total_mm"],
            "official_storm_context": xunxian_summary["official_precip_note"],
            "mean_daily_rh90_hours": xunxian_summary["mean_daily_rh90_hours"],
            "mean_daily_dpd_physical_hours": xunxian_summary["mean_daily_dpd_physical_hours"],
            "dominant_risk_label": xunxian_summary["dominant_risk_label"],
        },
        {
            "event_id": zhuozhou_summary["event_id"],
            "county": "保定涿州 (2023)",
            "flood_type": zhuozhou_summary["flood_type"],
            "s1_scenes_count": zhuozhou_summary["s1_scenes_count"],
            "peak_sample_grid": zhuozhou_summary["peak_sample_field"],
            "peak_date": zhuozhou_summary["peak_date"],
            "peak_flooded_pct": zhuozhou_summary["peak_flooded_pct"],
            "followup_date": zhuozhou_summary["followup_date"],
            "followup_flooded_pct": zhuozhou_summary["followup_flooded_pct"],
            "control_peak_pct": zhuozhou_summary["control_peak_pct"],
            "reanalysis_storm_open_meteo_mm": zhuozhou_summary["open_meteo_storm_total_mm"],
            "reanalysis_storm_nasa_power_mm": zhuozhou_summary["nasa_power_storm_total_mm"],
            "official_storm_context": zhuozhou_summary["official_precip_note"],
            "mean_daily_rh90_hours": zhuozhou_summary["mean_daily_rh90_hours"],
            "mean_daily_dpd_physical_hours": zhuozhou_summary["mean_daily_dpd_physical_hours"],
            "dominant_risk_label": zhuozhou_summary["dominant_risk_label"],
        },
    ]
    comp = pd.DataFrame(rows)
    comp.to_csv(
        OUT_DIR / "multi_event_comparison_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return comp


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reuse_sar = "--reuse-sar" in sys.argv

    _write_geojson(XUNXIAN_SPEC)
    x_sar_path = OUT_DIR / f"{XUNXIAN_SPEC.slug}_sar_flood_metrics.csv"
    x_sar = pd.read_csv(x_sar_path) if (reuse_sar and x_sar_path.is_file()) else _build_sar(XUNXIAN_SPEC)
    x_weather = _build_weather(XUNXIAN_SPEC)
    _, x_summary = _build_xunxian_timeline(x_weather, x_sar)

    _write_geojson(ZHUOZHOU_SPEC)
    z_sar_path = OUT_DIR / f"{ZHUOZHOU_SPEC.slug}_sar_flood_metrics.csv"
    z_sar = pd.read_csv(z_sar_path) if (reuse_sar and z_sar_path.is_file()) else _build_sar(ZHUOZHOU_SPEC)
    z_weather = _build_weather(ZHUOZHOU_SPEC)
    _, z_summary = _build_zhuozhou_timeline(z_weather, z_sar)

    comp = build_three_event_comparison(x_summary, z_summary)
    print(
        json.dumps(
            {
                "xunxian_2021": x_summary,
                "zhuozhou_2023": z_summary,
                "comparison_rows": len(comp),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
