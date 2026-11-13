from __future__ import annotations

from io import BytesIO

import pandas as pd

from case_pack import DEFAULT_CASE_ID, get_case_pack
from risk_engine import FieldScenario, assess


SCOPE_COLUMNS = [
    "case_id",
    "region_code",
    "country_code",
    "admin_level_1",
    "admin_level_2",
    "crop_code",
]
UNIT_COLUMNS = [
    "yield_kg_ha",
    "intervention_cost_per_ha",
    "currency_code",
]
METADATA_COLUMNS = [
    "record_id",
    "field_id",
    *SCOPE_COLUMNS,
    "observation_date",
    "observer",
    "county",
    "village",
    "plot_code",
    "longitude",
    "latitude",
    "flood_start_date",
    "drainage_date",
    "max_water_depth_cm",
    "first_symptom_date",
    "weather_source",
    "flood_source",
    "disease_source",
    "intervention_summary",
    "intervention_cost_yuan_per_mu",
    "yield_kg_per_mu",
    "yield_loss_pct",
    *UNIT_COLUMNS,
    "evidence_level",
    "notes",
]
SCENARIO_COLUMNS = [
    "crop_stage",
    "flood_days",
    "waterlog_days",
    "drainage_delay_hours",
    "standing_water",
    "target_disease",
    "symptom_status",
    "diagnosis_status",
    "pre_flood_baseline",
    "cultivar_name",
    "disease_pressure",
    "temperature_c",
    "humidity_pct",
    "wind_speed_ms",
]
TEMPLATE_COLUMNS = METADATA_COLUMNS + SCENARIO_COLUMNS
REQUIRED_COLUMNS = ["field_id", *SCENARIO_COLUMNS]
RESULT_COLUMNS = [
    *METADATA_COLUMNS,
    *SCENARIO_COLUMNS,
    "data_completeness",
    "risk_label",
    "surface_water_status",
    "waterlogging_status",
    "environment_suitability",
    "field_evidence_status",
    "regional_flood_status",
    "drainage_status",
    "treatment_status",
    "missing_inputs",
]


def template_csv() -> bytes:
    return pd.DataFrame(columns=TEMPLATE_COLUMNS).to_csv(
        index=False,
        encoding="utf-8-sig",
    ).encode("utf-8-sig")


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return pd.read_csv(
                BytesIO(data),
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
            )
        except UnicodeDecodeError as error:
            last_error = error
    raise ValueError("CSV编码无法识别，请使用UTF-8或GB18030保存。") from last_error


def _text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _number(
    value: object,
    column: str,
    row_number: int,
    errors: list[dict[str, str]],
) -> float | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        errors.append(
            {
                "行号": str(row_number),
                "字段": column,
                "错误": f"不是有效数值：{text}",
            }
        )
        return None


def _standing_water(
    value: object,
    row_number: int,
    errors: list[dict[str, str]],
) -> bool | None:
    text = (_text(value) or "unknown").lower()
    if text in {"unknown", "未知", ""}:
        return None
    if text in {"yes", "true", "1", "是", "有"}:
        return True
    if text in {"no", "false", "0", "否", "无"}:
        return False
    errors.append(
        {
            "行号": str(row_number),
            "字段": "standing_water",
            "错误": f"应为 yes/no/unknown，实际为：{text}",
        }
    )
    return None


def assess_csv(data: bytes) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = read_csv_bytes(data)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        errors = pd.DataFrame(
            [
                {
                    "行号": "文件",
                    "字段": column,
                    "错误": "缺少必需列",
                }
                for column in missing_columns
            ],
            columns=["行号", "字段", "错误"],
        )
        return pd.DataFrame(columns=RESULT_COLUMNS), errors

    results: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    for index, row in frame.iterrows():
        row_number = index + 2
        row_error_count = len(errors)
        field_id = _text(row.get("field_id"))
        if field_id is None:
            errors.append(
                {
                    "行号": str(row_number),
                    "字段": "field_id",
                    "错误": "田块编号不能为空",
                }
            )
            continue

        try:
            case_id = _text(row.get("case_id")) or DEFAULT_CASE_ID
            pack = get_case_pack(case_id)
            scenario = FieldScenario(
                crop_stage=_text(row.get("crop_stage")),
                flood_days=_number(row.get("flood_days"), "flood_days", row_number, errors),
                waterlog_days=_number(
                    row.get("waterlog_days"), "waterlog_days", row_number, errors
                ),
                drainage_delay_hours=_number(
                    row.get("drainage_delay_hours"),
                    "drainage_delay_hours",
                    row_number,
                    errors,
                ),
                standing_water=_standing_water(
                    row.get("standing_water"), row_number, errors
                ),
                target_disease=_text(row.get("target_disease")),
                symptom_status=_text(row.get("symptom_status")),
                diagnosis_status=_text(row.get("diagnosis_status")) or "not_assessed",
                pre_flood_baseline=_text(row.get("pre_flood_baseline")) or "unknown",
                cultivar_name=_text(row.get("cultivar_name")) or "unknown",
                disease_pressure=_text(row.get("disease_pressure")) or "unknown",
                temperature_c=_number(
                    row.get("temperature_c"), "temperature_c", row_number, errors
                ),
                humidity_pct=_number(
                    row.get("humidity_pct"), "humidity_pct", row_number, errors
                ),
                wind_speed_ms=_number(
                    row.get("wind_speed_ms"), "wind_speed_ms", row_number, errors
                ),
                case_id=case_id,
            )
            if len(errors) > row_error_count:
                continue
            assessment = assess(scenario)
        except (TypeError, ValueError) as error:
            errors.append(
                {
                    "行号": str(row_number),
                    "字段": "scenario",
                    "错误": str(error),
                }
            )
            continue

        result = {column: row.get(column, "") for column in TEMPLATE_COLUMNS}
        result.update(
            {
                "case_id": scenario.case_id,
                "region_code": _text(row.get("region_code")) or pack.region_code,
                "country_code": _text(row.get("country_code")) or pack.country_code,
                "crop_code": _text(row.get("crop_code")) or pack.crop_code,
                "currency_code": (
                    _text(row.get("currency_code"))
                    or str(pack.config.get("currency_code") or "")
                ),
                "crop_stage": scenario.crop_stage or "",
                "flood_days": scenario.flood_days,
                "waterlog_days": scenario.waterlog_days,
                "drainage_delay_hours": scenario.drainage_delay_hours,
                "standing_water": (
                    "unknown"
                    if scenario.standing_water is None
                    else "yes"
                    if scenario.standing_water
                    else "no"
                ),
                "target_disease": scenario.target_disease or "",
                "symptom_status": scenario.symptom_status or "",
                "diagnosis_status": scenario.diagnosis_status,
                "pre_flood_baseline": scenario.pre_flood_baseline,
                "cultivar_name": scenario.cultivar_name,
                "disease_pressure": scenario.disease_pressure or "unknown",
                "temperature_c": scenario.temperature_c,
                "humidity_pct": scenario.humidity_pct,
                "wind_speed_ms": scenario.wind_speed_ms,
                "data_completeness": assessment.data_completeness,
                "risk_label": assessment.risk_label,
                "surface_water_status": assessment.surface_water_status,
                "waterlogging_status": assessment.waterlogging_status,
                "environment_suitability": assessment.environment_suitability,
                "field_evidence_status": assessment.field_evidence_status,
                "regional_flood_status": assessment.regional_flood_class,
                "drainage_status": assessment.windows[0].status,
                "treatment_status": assessment.windows[3].status,
                "missing_inputs": "、".join(assessment.missing_inputs),
            }
        )
        results.append(result)

    return (
        pd.DataFrame(results, columns=RESULT_COLUMNS),
        pd.DataFrame(errors, columns=["行号", "字段", "错误"]),
    )


def result_csv(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
