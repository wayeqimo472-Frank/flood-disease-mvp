from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DATA = PROJECT_DIR.parent / "additional data" / "raw_data"
OUTPUT_DIR = PROJECT_DIR / "data" / "public_evidence_v0.2"


def build_one_acre_summary() -> dict[str, int]:
    source = (
        RAW_DATA
        / "one_acre_fund_maize_survey_2016_2022"
        / "One_Acre_Fund_MEL_maize_survey_data_2016-2022.csv"
    )
    frame = pd.read_csv(source)
    summary = (
        frame.groupby(["country", "water_excess", "disease"], dropna=False)
        .agg(
            fields=("yield_kg_ha", "size"),
            mean_yield_kg_ha=("yield_kg_ha", "mean"),
            median_yield_kg_ha=("yield_kg_ha", "median"),
        )
        .reset_index()
    )
    summary.to_csv(
        OUTPUT_DIR / "one_acre_exposure_disease_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    overall = (
        frame.groupby(["water_excess", "disease"], dropna=False)
        .agg(
            fields=("yield_kg_ha", "size"),
            mean_yield_kg_ha=("yield_kg_ha", "mean"),
            median_yield_kg_ha=("yield_kg_ha", "median"),
        )
        .reset_index()
    )
    baseline = float(
        overall.loc[
            (~overall["water_excess"]) & (~overall["disease"]),
            "mean_yield_kg_ha",
        ].iloc[0]
    )
    overall["mean_difference_vs_no_exposure_kg_ha"] = (
        overall["mean_yield_kg_ha"] - baseline
    )
    overall.to_csv(
        OUTPUT_DIR / "one_acre_overall_exposure_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    both = frame[frame["water_excess"] & frame["disease"]].copy()
    both["water_excess"] = True
    both["disease"] = True
    both.to_csv(
        OUTPUT_DIR / "one_acre_water_and_disease_fields.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return {
        "source_rows": len(frame),
        "water_excess_fields": int(frame["water_excess"].sum()),
        "disease_affected_fields": int(frame["disease"].sum()),
        "both_fields": len(both),
    }


def load_divine_leaf_wetness() -> pd.DataFrame:
    source_dir = RAW_DATA / "divine_leaf_wetness_granada_2023_2024"
    source = next(source_dir.glob("*_Year_*.csv"))
    frame = pd.read_csv(source, sep=",", encoding="cp1252", skiprows=5)
    frame["timestamp"] = pd.to_datetime(
        frame["Date & Time"],
        errors="coerce",
        dayfirst=True,
        format="mixed",
    )
    numeric_columns = {
        "Temp - °C": "temperature_c",
        "Hum - %": "rh_pct",
        "Lluvia - mm": "rain_mm",
        "Velocidad del viento - km/h": "wind_kmh",
        "Humedad del suelo  cm - cb": "soil_moisture_cb_node1",
        "Humedad del viento  cm - cb": "unused_node1",
        "Humedad foliar": "leaf_wetness_node1",
        "Minutos- Humedad foliar": "leaf_wetness_minutes_node1",
        "Humedad del suelo  cm - cb.1": "soil_moisture_cb_node2",
        "Humedad foliar.1": "leaf_wetness_node2",
        "Minutos- Humedad foliar.1": "leaf_wetness_minutes_node2",
    }
    tidy = pd.DataFrame({"timestamp": frame["timestamp"]})
    for source_column, target_column in numeric_columns.items():
        if source_column in frame:
            tidy[target_column] = pd.to_numeric(frame[source_column], errors="coerce")
    tidy = tidy.drop(columns=["unused_node1"], errors="ignore").dropna(
        subset=["timestamp"]
    )
    return tidy


def build_divine_leaf_wetness() -> dict[str, int | str]:
    tidy = load_divine_leaf_wetness()
    tidy.to_csv(
        OUTPUT_DIR / "divine_leaf_wetness_hourly.csv",
        index=False,
        encoding="utf-8-sig",
    )
    tidy["date"] = tidy["timestamp"].dt.date
    daily = (
        tidy.groupby("date")
        .agg(
            observed_hours=("timestamp", "size"),
            mean_temperature_c=("temperature_c", "mean"),
            mean_rh_pct=("rh_pct", "mean"),
            rain_mm=("rain_mm", "sum"),
            lwd_hours_node1=("leaf_wetness_minutes_node1", lambda value: value.sum() / 60),
            lwd_hours_node2=("leaf_wetness_minutes_node2", lambda value: value.sum() / 60),
        )
        .reset_index()
    )
    daily.to_csv(
        OUTPUT_DIR / "divine_leaf_wetness_daily.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return {
        "hourly_rows": len(tidy),
        "daily_rows": len(daily),
        "start": str(tidy["timestamp"].min()),
        "end": str(tidy["timestamp"].max()),
    }


def confusion_row(
    *,
    dataset: str,
    site_id: str,
    surface: str,
    actual: pd.Series,
    proxy: pd.Series,
) -> dict[str, object]:
    valid = actual.notna() & proxy.notna()
    actual_bool = actual[valid].astype(bool)
    proxy_bool = proxy[valid].astype(bool)
    tp = int((actual_bool & proxy_bool).sum())
    fp = int((~actual_bool & proxy_bool).sum())
    fn = int((actual_bool & ~proxy_bool).sum())
    tn = int((~actual_bool & ~proxy_bool).sum())
    actual_wet = tp + fn
    proxy_wet = tp + fp
    return {
        "dataset": dataset,
        "site_id": site_id,
        "surface": surface,
        "hourly_n": int(valid.sum()),
        "actual_wet_hours": actual_wet,
        "proxy_wet_hours": proxy_wet,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "sensitivity": tp / actual_wet if actual_wet else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "precision": tp / proxy_wet if proxy_wet else None,
        "agreement": (tp + tn) / int(valid.sum()) if int(valid.sum()) else None,
    }


def build_lwd_proxy_validation() -> dict[str, int]:
    rows: list[dict[str, object]] = []
    divine = load_divine_leaf_wetness()
    proxy = (divine["rh_pct"] >= 90).where(divine["rh_pct"].notna(), pd.NA)
    for node in (1, 2):
        wet_minutes = divine[f"leaf_wetness_minutes_node{node}"]
        actual = wet_minutes.apply(
            lambda value: pd.NA if pd.isna(value) else bool(value > 0)
        )
        rows.append(
            confusion_row(
                dataset="DIVINE Spain",
                site_id="DIEZMA",
                surface=f"node{node}",
                actual=actual,
                proxy=proxy,
            )
        )

    italy_dir = RAW_DATA / "leaf_wetness_agromet_italy_2025"
    site_metadata = json.loads((italy_dir / "sites.json").read_text(encoding="utf-8"))
    for site in site_metadata["sites"]:
        frame = pd.read_csv(italy_dir / site["ref"])
        proxy = (frame["rh"] >= 90).where(frame["rh"].notna(), pd.NA)
        for surface in ("leaf_top", "leaf_bot"):
            actual = frame[surface].apply(
                lambda value: pd.NA if pd.isna(value) else bool(value > 0)
            )
            rows.append(
                confusion_row(
                    dataset="Italy 7-site",
                    site_id=site["ref"],
                    surface=surface,
                    actual=actual,
                    proxy=proxy,
                )
            )
    output = pd.DataFrame(rows)
    output.to_csv(
        OUTPUT_DIR / "lwd_rh90_proxy_validation.csv",
        index=False,
        encoding="utf-8-sig",
    )
    summary = (
        output.groupby("dataset")
        .agg(
            comparisons=("site_id", "size"),
            mean_sensitivity=("sensitivity", "mean"),
            mean_specificity=("specificity", "mean"),
            mean_precision=("precision", "mean"),
            mean_agreement=("agreement", "mean"),
        )
        .reset_index()
    )
    summary.to_csv(
        OUTPUT_DIR / "lwd_rh90_proxy_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return {"comparison_rows": len(output)}


def build_flood_tolerant_plots() -> dict[str, int]:
    source = (
        RAW_DATA
        / "flood_tolerant_maize_uav_2020_2021"
        / "Plot_info.xlsx"
    )
    frame = pd.read_excel(source, sheet_name="Plot_data_Yield")
    numeric = {
        "Plot area (ft2)": "plot_area_ft2",
        "Stand Count [# of plants]": "stand_count",
        "Root Lodging [# of plants]": "root_lodging",
        "Stalk Lodging [# of plants]": "stalk_lodging",
        "Grain Moisture [%]": "grain_moisture_pct",
        "Plot Weight [lbs]": "plot_weight_lb",
    }
    output = frame[
        ["Year", "Location", "FIELD", "Plot_ID", "Pedigree", "Comments"]
    ].rename(
        columns={
            "Year": "year",
            "Location": "location",
            "FIELD": "field_id",
            "Plot_ID": "plot_id",
            "Pedigree": "pedigree",
            "Comments": "comments",
        }
    )
    for source_column, target_column in numeric.items():
        output[target_column] = pd.to_numeric(frame[source_column], errors="coerce")
    output["standing_water_comment"] = (
        output["comments"].fillna("").str.contains("standing water", case=False)
    )
    area_m2 = output["plot_area_ft2"] * 0.09290304
    output["yield_kg_ha_15_5"] = (
        output["plot_weight_lb"]
        * 0.45359237
        * (100 - output["grain_moisture_pct"])
        / (100 - 15.5)
        / area_m2
        * 10000
    )
    output.to_csv(
        OUTPUT_DIR / "flood_tolerant_maize_2020_plots.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return {
        "plot_rows": len(output),
        "standing_water_comment_rows": int(output["standing_water_comment"].sum()),
        "derived_yield_rows": int(output["yield_kg_ha_15_5"].notna().sum()),
    }


def build_italy_leaf_wetness_summary() -> dict[str, int]:
    source_dir = RAW_DATA / "leaf_wetness_agromet_italy_2025"
    site_metadata = json.loads((source_dir / "sites.json").read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for site in site_metadata["sites"]:
        frame = pd.read_csv(source_dir / site["ref"])
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
        rows.append(
            {
                "site_file": site["ref"],
                "latitude": site["lat"],
                "longitude": site["lon"],
                "elevation_m": site["elevation"],
                "start": frame["time"].min(),
                "end": frame["time"].max(),
                "rows": len(frame),
                "mean_leaf_top": frame["leaf_top"].mean(),
                "mean_leaf_bot": frame["leaf_bot"].mean(),
                "mean_temperature_c": frame["temperature"].mean(),
                "mean_rh_pct": frame["rh"].mean(),
                "total_rain_mm": frame["rain"].sum(),
            }
        )
    summary = pd.DataFrame(rows)
    summary.to_csv(
        OUTPUT_DIR / "italy_leaf_wetness_site_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return {"sites": len(summary), "hourly_rows": int(summary["rows"].sum())}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "one_acre_fund": build_one_acre_summary(),
        "divine_leaf_wetness": build_divine_leaf_wetness(),
        "lwd_rh90_proxy_validation": build_lwd_proxy_validation(),
        "flood_tolerant_maize": build_flood_tolerant_plots(),
        "italy_leaf_wetness": build_italy_leaf_wetness_summary(),
        "boundary": (
            "These outputs keep source datasets separate. "
            "They are not a joined causal flood-disease dataset."
        ),
    }
    (OUTPUT_DIR / "evidence_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
