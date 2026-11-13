from __future__ import annotations

import json
import sys
from hashlib import md5
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
CASE_DIR = PROJECT_DIR / "case_packs" / "us_corn_belt_cscap_2011_2015"
RAW_DIR = CASE_DIR / "raw"
PROCESSED_DIR = CASE_DIR / "processed"
WORKBOOK = RAW_DIR / "Sustainable_Corn_Research_Data_2011-2015.xlsx"
EXPECTED_MD5 = "34d284bb59f549e25ea9f77b33721003"
CASE_ID = "us_corn_belt_cscap_2011_2015"


def read_sheet(name: str) -> pd.DataFrame:
    raw = pd.read_excel(WORKBOOK, sheet_name=name, header=None)
    frame = raw.iloc[2:].copy()
    frame.columns = [str(value) for value in raw.iloc[0]]
    return frame.reset_index(drop=True)


def clean_text(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text if text and text.lower() not in {"nan", "none"} else None


def disease_mapping(name: str) -> tuple[str, str]:
    lowered = name.lower()
    if "gray leaf spot" in lowered:
        return "gray_leaf_spot", "confirmed_fungal"
    if "ear rot" in lowered:
        return "ear_rot", "confirmed_fungal"
    if "stalk rot" in lowered:
        return "stalk_rot", "confirmed_fungal"
    if "stewart" in lowered:
        return "stewarts_wilt", "confirmed_nonfungal"
    return "other_disease", "confirmed_nonfungal"


def main() -> None:
    actual_md5 = md5(WORKBOOK.read_bytes()).hexdigest()
    if actual_md5 != EXPECTED_MD5:
        raise ValueError(f"工作簿MD5不匹配：{actual_md5}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    sites = read_sheet("Site Metadata")
    sites["uniqueid"] = sites["uniqueid"].map(clean_text)
    sites = sites[sites["uniqueid"].ne("units") & sites["uniqueid"].notna()].copy()
    for column in ["NW Lon", "NW Lat", "SW Lon", "SW Lat", "SE Lon", "SE Lat", "NE Lon", "NE Lat"]:
        sites[column] = pd.to_numeric(sites[column], errors="coerce")
    sites["longitude"] = sites[["NW Lon", "SW Lon", "SE Lon", "NE Lon"]].mean(axis=1)
    sites["latitude"] = sites[["NW Lat", "SW Lat", "SE Lat", "NE Lat"]].mean(axis=1)
    site_output = sites[
        ["uniqueid", "state", "county", "city", "longitude", "latitude", "site area", "number of plots"]
    ].rename(
        columns={
            "uniqueid": "site_id",
            "state": "state",
            "county": "county",
            "city": "city",
            "site area": "site_area",
            "number of plots": "plot_count",
        }
    )
    site_output.to_csv(PROCESSED_DIR / "site_metadata.csv", index=False, encoding="utf-8-sig")

    plots = read_sheet("Plot Identifiers")
    plots["uniqueid"] = plots["uniqueid"].map(clean_text)
    plots["plotid"] = plots["plotid"].astype(str).str.strip()
    plots = plots[plots["uniqueid"].ne("units") & plots["uniqueid"].notna()].copy()
    crop_rows: list[dict[str, object]] = []
    for _, row in plots.iterrows():
        for year in range(2011, 2016):
            crop = clean_text(row.get(f"{year}crop"))
            if crop:
                crop_rows.append(
                    {
                        "site_id": row["uniqueid"],
                        "plot_id": row["plotid"],
                        "year": year,
                        "crop": crop.lower(),
                        "tillage": row.get("tillage"),
                        "rotation": row.get("rotation"),
                        "drainage": row.get("drainage"),
                        "nitrogen": row.get("nitrogen"),
                        "landscape": row.get("landscape"),
                    }
                )
    plot_crops = pd.DataFrame(crop_rows)

    agronomy = read_sheet("Agronomic")
    agronomy["uniqueid"] = agronomy["uniqueid"].map(clean_text)
    agronomy["plotid"] = agronomy["plotid"].astype(str).str.strip()
    agronomy["year"] = pd.to_numeric(agronomy["year"], errors="coerce")
    agronomy["yield_kg_ha"] = pd.to_numeric(agronomy["AGR17"], errors="coerce")
    corn_yield = agronomy[
        agronomy["uniqueid"].ne("units")
        & agronomy["uniqueid"].notna()
        & agronomy["yield_kg_ha"].notna()
    ][["uniqueid", "plotid", "year", "yield_kg_ha"]].rename(
        columns={"uniqueid": "site_id", "plotid": "plot_id"}
    )
    corn_yield["year"] = corn_yield["year"].astype(int)
    corn_yield = corn_yield.merge(
        plot_crops[["site_id", "plot_id", "year", "crop"]],
        on=["site_id", "plot_id", "year"],
        how="left",
    )
    corn_yield = corn_yield[corn_yield["crop"].eq("corn")]
    corn_yield.to_csv(
        PROCESSED_DIR / "corn_yield.csv",
        index=False,
        encoding="utf-8-sig",
    )

    ipm = read_sheet("IPM")
    ipm["uniqueid"] = ipm["uniqueid"].map(clean_text)
    ipm["plotid"] = ipm["plotid"].astype(str).str.strip()
    ipm["date"] = pd.to_datetime(ipm["date"], errors="coerce", format="mixed")
    ipm["year_numeric"] = pd.to_numeric(ipm["year"], errors="coerce").fillna(
        ipm["date"].dt.year
    )
    ipm["severity_pct"] = pd.to_numeric(ipm["IPM14"], errors="coerce")
    ipm["plant"] = ipm["IPM10"].map(clean_text)
    ipm["disease_name"] = ipm["IPM12"].map(clean_text)
    disease_rows = ipm[
        ipm["uniqueid"].ne("units")
        & ipm["uniqueid"].notna()
        & ipm["plant"].eq("Corn")
        & ipm["disease_name"].notna()
        & ipm["severity_pct"].notna()
    ].copy()
    mapping = disease_rows["disease_name"].map(disease_mapping)
    disease_rows["disease_code"] = mapping.map(lambda value: value[0])
    disease_rows["diagnosis_status"] = mapping.map(lambda value: value[1])
    disease_rows["year"] = disease_rows["year_numeric"].astype("Int64")
    disease_rows["severity_scale"] = "percent"
    disease_ratings = disease_rows[
        [
            "uniqueid",
            "plotid",
            "date",
            "year",
            "disease_name",
            "disease_code",
            "severity_pct",
            "severity_scale",
            "IPM11",
            "IPM13",
            "diagnosis_status",
        ]
    ].rename(
        columns={
            "uniqueid": "site_id",
            "plotid": "plot_id",
            "IPM11": "plant_component",
            "IPM13": "canopy_position",
        }
    )
    disease_ratings.to_csv(
        PROCESSED_DIR / "disease_ratings.csv",
        index=False,
        encoding="utf-8-sig",
    )

    disease_yield = disease_ratings.merge(
        corn_yield[["site_id", "plot_id", "year", "yield_kg_ha"]],
        on=["site_id", "plot_id", "year"],
        how="left",
    )
    disease_yield.to_csv(
        PROCESSED_DIR / "disease_yield_matched.csv",
        index=False,
        encoding="utf-8-sig",
    )

    water_table = read_sheet("Water_Water Table")
    water_table["uniqueid"] = water_table["uniqueid"].map(clean_text)
    water_table["plotid"] = water_table["plotid"].astype(str).str.strip()
    water_table["date"] = pd.to_datetime(
        water_table["date"], errors="coerce", format="mixed"
    )
    water_table["depth_mm"] = pd.to_numeric(water_table["Depth (mm)"], errors="coerce")
    water_table = water_table[
        water_table["uniqueid"].ne("units")
        & water_table["uniqueid"].notna()
        & water_table["date"].notna()
        & water_table["depth_mm"].notna()
    ][["uniqueid", "plotid", "date", "depth_mm"]].rename(
        columns={"uniqueid": "site_id", "plotid": "plot_id"}
    )
    water_table["year"] = water_table["date"].dt.year
    water_table.to_csv(
        PROCESSED_DIR / "water_table_daily.csv",
        index=False,
        encoding="utf-8-sig",
    )

    tile_flow = read_sheet("Water_Tile Flow")
    tile_flow["uniqueid"] = tile_flow["uniqueid"].map(clean_text)
    tile_flow["plotid"] = tile_flow["plotid"].astype(str).str.strip()
    tile_flow["date"] = pd.to_datetime(
        tile_flow["date"], errors="coerce", format="mixed"
    )
    tile_flow["discharge_mm"] = pd.to_numeric(
        tile_flow["Discharge (mm)"],
        errors="coerce",
    )
    tile_flow = tile_flow[
        tile_flow["uniqueid"].ne("units")
        & tile_flow["uniqueid"].notna()
        & tile_flow["date"].notna()
        & tile_flow["discharge_mm"].notna()
    ][["uniqueid", "plotid", "date", "discharge_mm"]].rename(
        columns={"uniqueid": "site_id", "plotid": "plot_id"}
    )
    tile_flow["year"] = tile_flow["date"].dt.year
    tile_flow.to_csv(
        PROCESSED_DIR / "tile_flow_daily.csv",
        index=False,
        encoding="utf-8-sig",
    )

    operations = read_sheet("Field Operations")
    operations["uniqueid"] = operations["uniqueid"].map(clean_text)
    operations["cropyear"] = pd.to_numeric(operations["cropyear"], errors="coerce")
    operations["date"] = pd.to_datetime(
        operations["date"], errors="coerce", format="mixed"
    )
    operations = operations[
        operations["uniqueid"].ne("units") & operations["uniqueid"].notna()
    ].rename(columns={"uniqueid": "site_id"})
    operations.to_csv(
        PROCESSED_DIR / "field_operations.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pesticides = read_sheet("Pesticides")
    pesticides["uniqueid"] = pesticides["uniqueid"].map(clean_text)
    pesticides["cropyear"] = pd.to_numeric(pesticides["cropyear"], errors="coerce")
    pesticides["date"] = pd.to_datetime(
        pesticides["date"], errors="coerce", format="mixed"
    )
    pesticides = pesticides[
        pesticides["uniqueid"].ne("units") & pesticides["uniqueid"].notna()
    ].rename(columns={"uniqueid": "site_id"})
    pesticides.to_csv(
        PROCESSED_DIR / "pesticides.csv",
        index=False,
        encoding="utf-8-sig",
    )

    site_lookup = site_output.set_index("site_id").to_dict(orient="index")
    canonical = (
        disease_yield.groupby(
            ["site_id", "plot_id", "date", "year", "disease_code", "diagnosis_status"],
            dropna=False,
        )
        .agg(
            severity_pct=("severity_pct", "max"),
            yield_kg_ha=("yield_kg_ha", "mean"),
            source_disease_names=("disease_name", lambda values: "; ".join(sorted(set(values)))),
        )
        .reset_index()
    )
    observations: list[dict[str, object]] = []
    for index, row in canonical.iterrows():
        site = site_lookup.get(row["site_id"], {})
        severity = float(row["severity_pct"])
        symptom = "none" if severity == 0 else "obvious"
        observations.append(
            {
                "record_id": f"US-CSCAP-{index + 1:05d}",
                "field_id": f"{row['site_id']}:{row['plot_id']}",
                "case_id": CASE_ID,
                "region_code": f"US-{site.get('state', '')}",
                "country_code": "US",
                "admin_level_1": site.get("state"),
                "admin_level_2": site.get("county"),
                "crop_code": "maize",
                "observation_date": (
                    row["date"].date().isoformat() if pd.notna(row["date"]) else ""
                ),
                "observer": "Sustainable Corn CAP",
                "yield_kg_ha": (
                    round(float(row["yield_kg_ha"]), 3)
                    if pd.notna(row["yield_kg_ha"])
                    else ""
                ),
                "currency_code": "USD",
                "evidence_level": "EXTERNAL_OBSERVED",
                "notes": (
                    f"Source disease: {row['source_disease_names']}; "
                    f"severity {severity:g}%"
                ),
                "target_disease": row["disease_code"],
                "symptom_status": symptom,
                "diagnosis_status": row["diagnosis_status"],
                "pre_flood_baseline": "unknown",
                "cultivar_name": "other",
                "disease_pressure": "unknown",
            }
        )
    from batch_io import TEMPLATE_COLUMNS

    observations_frame = pd.DataFrame(observations)
    for column in TEMPLATE_COLUMNS:
        if column not in observations_frame:
            observations_frame[column] = ""
    observations_frame = observations_frame[TEMPLATE_COLUMNS]
    observations_frame.to_csv(
        PROCESSED_DIR / "observations_v0.6.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary = {
        "case_id": CASE_ID,
        "source_workbook_md5": actual_md5,
        "sites": int(site_output["site_id"].nunique()),
        "corn_yield_rows": int(len(corn_yield)),
        "disease_rating_rows": int(len(disease_ratings)),
        "disease_yield_rows": int(disease_yield["yield_kg_ha"].notna().sum()),
        "disease_observation_rows": int(len(observations_frame)),
        "water_table_daily_rows": int(len(water_table)),
        "tile_flow_daily_rows": int(len(tile_flow)),
        "field_operation_rows": int(len(operations)),
        "pesticide_rows": int(len(pesticides)),
        "states": sorted(site_output["state"].dropna().unique().tolist()),
        "diseases": sorted(disease_ratings["disease_code"].dropna().unique().tolist()),
        "limitation": (
            "No public field-level flood-disease time series was found. "
            "This case is an external observation and monitoring case, not local calibration."
        ),
    }
    (PROCESSED_DIR / "validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
