from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


TREATMENTS = {
    "control": ("对照", None, 0, 0),
    "early_4d": ("早期淹水", "1991-06-12", 4, 100),
    "early_8d": ("早期淹水", "1991-06-12", 8, 100),
    "late_4d": ("后期淹水", "1991-07-01", 4, 100),
    "late_8d": ("后期淹水", "1991-07-01", 8, 100),
}

DAILY_COLUMNS = {
    "SimulationName": "simulation_name",
    "_WL_": "treatment",
    "Clock.Today": "date",
    "Maize.Phenology.CurrentStageName": "crop_stage",
    "Maize.Leaf.LAI": "lai",
    "Maize.AboveGround.Wt": "aboveground_g_m2",
    "Maize.Root.WetRootFraction": "wet_root_fraction",
    "ExcessWaterStressToday": "excess_water_factor",
    "Maize.CumulativeExcessWaterStress": "cumulative_excess_water_stress",
    "SurfacePondingMm": "surface_ponding_mm",
    "Swim3.WaterTable": "water_table_mm",
    "Swim3.Drainage": "drainage_mm",
    "Swim3.SubsurfaceDrain": "subsurface_drain_mm",
}

SUMMARY_COLUMNS = [
    "simulation_name",
    "year",
    "treatment",
    "timing",
    "flood_start",
    "drainage_hold_days",
    "water_application_mm_day",
    "ponding_days",
    "max_surface_ponding_mm",
    "max_wet_root_fraction",
    "min_excess_water_factor",
    "cumulative_excess_water_stress",
    "max_lai",
    "max_biomass_kg_ha",
    "simulated_yield_kg_ha",
    "observed_yield_kg_ha",
    "simulated_yield_relative_to_control_pct",
    "observed_yield_relative_to_control_pct",
    "simulation_minus_observed_pct",
    "evidence_level",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(r"D:\APP\apsim_flood_disease\reference"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "simulation",
    )
    args = parser.parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    daily_source = source_dir / "MaizeLizaso_waterlogging.Report_Day.csv"
    predicted_source = source_dir / "MaizeLizaso_waterlogging.Report_Harvest.csv"
    observed_source = source_dir / "MaizeLizaso.Harvest.csv"
    model_source = source_dir / "MaizeLizaso_waterlogging.apsimx"
    weather_source = source_dir / "Lizaso.met"
    observation_source = source_dir / "LizasoObs.xlsx"

    daily_rows = [
        row
        for row in read_csv(daily_source)
        if row["SimulationName"].startswith("Exp4_1991_")
    ]
    predicted = {
        row["SimulationName"]: float(row["Maize.Grain.Wt"]) * 10
        for row in read_csv(predicted_source)
    }
    observed = {
        row["SimulationName"]: float(row["Observed.Maize.Grain.Wt"]) * 10
        for row in read_csv(observed_source)
    }

    daily_output = []
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in daily_rows:
        grouped[row["SimulationName"]].append(row)
        output_row = {
            target: row[source] for source, target in DAILY_COLUMNS.items()
        }
        output_row["aboveground_kg_ha"] = round(
            float(output_row.pop("aboveground_g_m2")) * 10,
            3,
        )
        daily_output.append(output_row)

    summaries = []
    for simulation_name, rows in grouped.items():
        first = rows[0]
        treatment = first["_WL_"]
        timing, flood_start, hold_days, water_mm_day = TREATMENTS[treatment]
        simulated_yield = predicted[simulation_name]
        observed_yield = observed[simulation_name]
        summaries.append(
            {
                "simulation_name": simulation_name,
                "year": 1991,
                "treatment": treatment,
                "timing": timing,
                "flood_start": flood_start or "",
                "drainage_hold_days": hold_days,
                "water_application_mm_day": water_mm_day,
                "ponding_days": sum(
                    float(row["SurfacePondingMm"]) > 0 for row in rows
                ),
                "max_surface_ponding_mm": round(
                    max(float(row["SurfacePondingMm"]) for row in rows),
                    3,
                ),
                "max_wet_root_fraction": round(
                    max(float(row["Maize.Root.WetRootFraction"]) for row in rows),
                    3,
                ),
                "min_excess_water_factor": round(
                    min(float(row["ExcessWaterStressToday"]) for row in rows),
                    3,
                ),
                "cumulative_excess_water_stress": round(
                    max(
                        float(row["Maize.CumulativeExcessWaterStress"])
                        for row in rows
                    ),
                    3,
                ),
                "max_lai": round(
                    max(float(row["Maize.Leaf.LAI"]) for row in rows),
                    3,
                ),
                "max_biomass_kg_ha": round(
                    max(float(row["Maize.AboveGround.Wt"]) for row in rows) * 10,
                    3,
                ),
                "simulated_yield_kg_ha": round(simulated_yield, 3),
                "observed_yield_kg_ha": round(observed_yield, 3),
                "evidence_level": "simulated_validation",
            }
        )

    control = next(row for row in summaries if row["treatment"] == "control")
    for row in summaries:
        row["simulated_yield_relative_to_control_pct"] = round(
            (row["simulated_yield_kg_ha"] / control["simulated_yield_kg_ha"] - 1)
            * 100,
            2,
        )
        row["observed_yield_relative_to_control_pct"] = round(
            (row["observed_yield_kg_ha"] / control["observed_yield_kg_ha"] - 1)
            * 100,
            2,
        )
        row["simulation_minus_observed_pct"] = round(
            (row["simulated_yield_kg_ha"] / row["observed_yield_kg_ha"] - 1)
            * 100,
            2,
        )

    summaries.sort(
        key=lambda row: (
            row["treatment"] != "control",
            row["flood_start"],
            row["drainage_hold_days"],
        )
    )
    write_csv(
        output_dir / "lizaso_maize_1991_summary.csv",
        SUMMARY_COLUMNS,
        summaries,
    )
    write_csv(
        output_dir / "lizaso_maize_1991_daily.csv",
        list(daily_output[0]),
        daily_output,
    )

    manifest = {
        "dataset_id": "apsim_lizaso_maize_1991_waterlogging",
        "evidence_level": "simulated_validation",
        "description": (
            "APSIM official maize flooding validation scenario, rerun locally "
            "with additional waterlogging diagnostics."
        ),
        "model": "APSIM 2026.11.8146.0",
        "validation_model_url": (
            "https://github.com/APSIMInitiative/ApsimX/blob/master/"
            "Tests/Validation/Maize/MaizeLizaso.apsimx"
        ),
        "weather_url": (
            "https://github.com/APSIMInitiative/ApsimX/blob/master/"
            "Tests/Validation/Maize/Lizaso.met"
        ),
        "observation_url": (
            "https://github.com/APSIMInitiative/ApsimX/blob/master/"
            "Tests/Validation/Maize/LizasoObs.xlsx"
        ),
        "yield_unit_source": "g/m2 multiplied by 10 to kg/ha",
        "inputs_sha256": {
            path.name: sha256(path)
            for path in (
                model_source,
                weather_source,
                observation_source,
                daily_source,
                predicted_source,
                observed_source,
            )
        },
        "scenario_count": len(summaries),
        "daily_row_count": len(daily_output),
        "not_for": [
            "河南本地定量校准",
            "南方锈病预测",
            "替代田块实测数据",
            "直接估计农户田块产量损失",
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output_dir)


if __name__ == "__main__":
    main()
