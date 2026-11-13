import pandas as pd
import streamlit as st

from risk_engine import assess
from ui_common import (
    BASELINE_LABELS,
    CULTIVAR_LABELS,
    CULTIVAR_NOTES,
    CUSTOM_SCENARIO,
    DATA_COMPLETENESS_LABELS,
    DEFAULT_PRESET,
    DIAGNOSIS_LABELS,
    DISEASE_LABELS,
    ENVIRONMENT_LABELS,
    ENVIRONMENT_METRIC_LABELS,
    FLOOD_CLASS_LABELS,
    PRESSURE_LABELS,
    SCENARIO_PRESETS,
    STAGE_LABELS,
    STANDING_WATER_LABELS,
    SYMPTOM_LABELS,
    current_source_label,
    render_assessment_status,
    render_metric_cards,
    render_priority_notice,
    render_safety_notices,
    save_current_state,
    scenario_from_inputs,
)


st.title("风险情景筛查")
st.caption("选择情景并输入当前田块信息，生成证据约束下的筛查结果。")

if "risk_preset" not in st.session_state:
    st.session_state.risk_preset = st.session_state.get("current_preset", DEFAULT_PRESET)
preset_name = st.selectbox(
    "快速情景",
    options=["自定义", *SCENARIO_PRESETS],
    key="risk_preset",
)
is_custom = preset_name == "自定义"
input_defaults = CUSTOM_SCENARIO if is_custom else SCENARIO_PRESETS[preset_name]

if is_custom:
    st.info("自定义情景：未填写的数值按数据缺失处理，不套用任何预设值。")
else:
    st.info(f"当前载入“{preset_name}”情景假设值，非田间实测。")
st.caption("数字输入修改后需按 Enter 或移出输入框才会应用；应用前结果仍对应上一次已提交数据。")


def _saved_value(field: str, fallback: object) -> object:
    if st.session_state.get("current_preset") == preset_name:
        return st.session_state.get("current_inputs", {}).get(field, fallback)
    return fallback


def _init_number(key: str, field: str, fallback: object) -> None:
    if key not in st.session_state:
        st.session_state[key] = _saved_value(field, fallback)


def _option_index(options: list[str], value: str | None) -> int | None:
    return None if value is None else options.index(value)


input_1, input_2, input_3 = st.columns(3, gap="large")

with input_1:
    st.subheader("1. 涝渍暴露")
    crop_stage_options = list(STAGE_LABELS)
    crop_stage = st.selectbox(
        "玉米生育期",
        options=crop_stage_options,
        index=_option_index(
            crop_stage_options, _saved_value("crop_stage", input_defaults["crop_stage"])
        ),
        format_func=STAGE_LABELS.get,
        key=f"crop_stage::{preset_name}",
        placeholder="请选择生育期",
    )
    flood_key = f"flood_days::{preset_name}"
    _init_number(flood_key, "flood_days", input_defaults["flood_days"])
    flood_days = st.number_input(
        "连续田面明水天数",
        min_value=0.0,
        max_value=30.0,
        value=None,
        step=0.5,
        key=flood_key,
        placeholder="缺失",
    )
    waterlog_key = f"waterlog_days::{preset_name}"
    _init_number(waterlog_key, "waterlog_days", input_defaults["waterlog_days"])
    waterlog_days = st.number_input(
        "无明水但土壤饱和/渍水天数",
        min_value=0.0,
        max_value=30.0,
        value=None,
        step=0.5,
        key=waterlog_key,
        placeholder="缺失",
    )
    drainage_key = f"drainage_delay_hours::{preset_name}"
    _init_number(
        drainage_key, "drainage_delay_hours", input_defaults["drainage_delay_hours"]
    )
    drainage_delay_hours = st.number_input(
        "从淹水开始到排水的时间（小时）",
        min_value=0.0,
        max_value=720.0,
        value=None,
        step=6.0,
        key=drainage_key,
        placeholder="缺失",
    )
    standing_value = _saved_value(
        "standing_water", input_defaults["standing_water"]
    )
    standing_default = (
        "unknown"
        if standing_value is None
        else "yes"
        if standing_value
        else "no"
    )
    standing_status = st.selectbox(
        "当前田面明水状态",
        options=list(STANDING_WATER_LABELS),
        index=list(STANDING_WATER_LABELS).index(standing_default),
        format_func=STANDING_WATER_LABELS.get,
        key=f"standing_water::{preset_name}",
    )
    standing_water = (
        None
        if standing_status == "unknown"
        else True
        if standing_status == "yes"
        else False
    )

with input_2:
    st.subheader("2. 病害与诊断")
    target_options = list(DISEASE_LABELS)
    target_disease = st.selectbox(
        "目标病害",
        options=target_options,
        index=_option_index(
            target_options,
            _saved_value("target_disease", input_defaults["target_disease"]),
        ),
        format_func=DISEASE_LABELS.get,
        key=f"target_disease::{preset_name}",
        placeholder="请选择目标病害",
    )
    symptom_options = list(SYMPTOM_LABELS)
    symptom_status = st.selectbox(
        "当前症状",
        options=symptom_options,
        index=_option_index(
            symptom_options,
            _saved_value("symptom_status", input_defaults["symptom_status"]),
        ),
        format_func=SYMPTOM_LABELS.get,
        key=f"symptom_status::{preset_name}",
        placeholder="请选择症状状态",
    )
    diagnosis_options = list(DIAGNOSIS_LABELS)
    diagnosis_status = st.selectbox(
        "诊断状态",
        options=diagnosis_options,
        index=_option_index(
            diagnosis_options,
            _saved_value("diagnosis_status", input_defaults["diagnosis_status"]),
        ),
        format_func=DIAGNOSIS_LABELS.get,
        key=f"diagnosis_status::{preset_name}",
    )
    baseline_options = list(BASELINE_LABELS)
    pre_flood_baseline = st.selectbox(
        "洪涝前病情基线",
        options=baseline_options,
        index=_option_index(
            baseline_options,
            _saved_value(
                "pre_flood_baseline", input_defaults["pre_flood_baseline"]
            ),
        ),
        format_func=BASELINE_LABELS.get,
        key=f"pre_flood_baseline::{preset_name}",
    )
    cultivar_options = list(CULTIVAR_LABELS)
    cultivar_name = st.selectbox(
        "案例主栽品种",
        options=cultivar_options,
        index=_option_index(
            cultivar_options,
            _saved_value("cultivar_name", input_defaults["cultivar_name"]),
        ),
        format_func=CULTIVAR_LABELS.get,
        key=f"cultivar_name::{preset_name}",
    )
    if cultivar_name in CULTIVAR_NOTES:
        st.caption(CULTIVAR_NOTES[cultivar_name])
    else:
        st.caption("品种身份已知；该主导品种缺少公开耐涝分级，不进行品种风险调整。")
    pressure_options = list(PRESSURE_LABELS)
    disease_pressure = st.selectbox(
        "周边病害压力或外部菌源",
        options=pressure_options,
        index=_option_index(
            pressure_options,
            _saved_value("disease_pressure", input_defaults["disease_pressure"]),
        ),
        format_func=PRESSURE_LABELS.get,
        key=f"disease_pressure::{preset_name}",
    )

with input_3:
    st.subheader("3. 环境与作业条件")
    temperature_key = f"temperature_c::{preset_name}"
    _init_number(temperature_key, "temperature_c", input_defaults["temperature_c"])
    temperature_c = st.number_input(
        "日平均温度（℃）",
        min_value=0.0,
        max_value=45.0,
        value=None,
        step=0.5,
        key=temperature_key,
        placeholder="缺失",
    )
    humidity_key = f"humidity_pct::{preset_name}"
    _init_number(humidity_key, "humidity_pct", input_defaults["humidity_pct"])
    humidity_pct = st.number_input(
        "平均相对湿度（%）",
        min_value=0.0,
        max_value=100.0,
        value=None,
        step=1.0,
        key=humidity_key,
        placeholder="缺失",
    )
    wind_key = f"wind_speed_ms::{preset_name}"
    _init_number(wind_key, "wind_speed_ms", input_defaults["wind_speed_ms"])
    wind_speed_ms = st.number_input(
        "预计作业风速（m/s）",
        min_value=0.0,
        max_value=30.0,
        value=None,
        step=0.5,
        key=wind_key,
        placeholder="缺失",
    )

inputs = {
    "crop_stage": crop_stage,
    "flood_days": flood_days,
    "waterlog_days": waterlog_days,
    "drainage_delay_hours": drainage_delay_hours,
    "standing_water": standing_water,
    "target_disease": target_disease,
    "symptom_status": symptom_status,
    "diagnosis_status": diagnosis_status,
    "pre_flood_baseline": pre_flood_baseline,
    "cultivar_name": cultivar_name,
    "disease_pressure": disease_pressure,
    "temperature_c": temperature_c,
    "humidity_pct": humidity_pct,
    "wind_speed_ms": wind_speed_ms,
}

modified_fields: list[str] = []
if not is_custom:
    comparisons = [
        ("玉米生育期", crop_stage, input_defaults["crop_stage"]),
        ("连续田面明水天数", flood_days, input_defaults["flood_days"]),
        ("土壤饱和/渍水天数", waterlog_days, input_defaults["waterlog_days"]),
        ("排水时间", drainage_delay_hours, input_defaults["drainage_delay_hours"]),
        ("田面明水状态", standing_water, input_defaults["standing_water"]),
        ("目标病害", target_disease, input_defaults["target_disease"]),
        ("当前症状", symptom_status, input_defaults["symptom_status"]),
        ("诊断状态", diagnosis_status, input_defaults["diagnosis_status"]),
        ("洪涝前病情基线", pre_flood_baseline, input_defaults["pre_flood_baseline"]),
        ("品种身份", cultivar_name, input_defaults["cultivar_name"]),
        ("周边病害压力", disease_pressure, input_defaults["disease_pressure"]),
        ("日平均温度", temperature_c, input_defaults["temperature_c"]),
        ("平均相对湿度", humidity_pct, input_defaults["humidity_pct"]),
        ("预计作业风速", wind_speed_ms, input_defaults["wind_speed_ms"]),
    ]
    modified_fields = [
        label for label, current, original in comparisons if current != original
    ]

if modified_fields:
    st.warning(
        "参数已修改：当前输入已不再完全等同于原始预设"
        f"（涉及：{'、'.join(modified_fields)}）。"
    )

scenario = scenario_from_inputs(inputs)
result = assess(scenario)
save_current_state(preset_name, inputs, result, modified_fields)

render_assessment_status()
st.subheader("决策摘要")
render_metric_cards(
    [
        ("数据完整性", DATA_COMPLETENESS_LABELS[result.data_completeness]),
        ("处置优先级", result.risk_label),
        (
            "涝渍暴露",
            f"明水{'缺失' if flood_days is None else f'{flood_days:g}天'} / "
            f"渍水{'缺失' if waterlog_days is None else f'{waterlog_days:g}天'}",
        ),
        ("田间证据", result.field_evidence_status),
        ("环境适宜度", ENVIRONMENT_METRIC_LABELS[result.environment_suitability]),
    ]
)

st.write(f"- {result.surface_water_status}")
st.write(f"- {result.waterlogging_status}")
if result.missing_inputs:
    st.caption(f"缺失或未知输入：{'、'.join(result.missing_inputs)}。")
st.caption(
    "环境与作业实际输入："
    f"温度={'缺失' if temperature_c is None else f'{temperature_c:g}℃'}；"
    f"湿度={'缺失' if humidity_pct is None else f'{humidity_pct:g}%'}；"
    f"风速={'缺失' if wind_speed_ms is None else f'{wind_speed_ms:g}m/s'}。"
)
st.caption(
    f"区域受淹分级（E14）：{FLOOD_CLASS_LABELS[result.regional_flood_class]}，"
    "未用田块明水天数替代；"
    f"环境判据：{ENVIRONMENT_LABELS[result.environment_suitability]}"
)

render_priority_notice(result)
render_safety_notices(result)
st.caption(result.stage_disease_note)

with st.expander("查看本次已提交输入与判断边界", expanded=False):
    submitted_rows = [
        ("情景", "情景来源", current_source_label()),
        ("涝渍暴露", "玉米生育期", STAGE_LABELS.get(crop_stage, "缺失")),
        ("涝渍暴露", "连续田面明水天数", "缺失" if flood_days is None else f"{flood_days:g}天"),
        ("涝渍暴露", "土壤饱和/渍水天数", "缺失" if waterlog_days is None else f"{waterlog_days:g}天"),
        ("涝渍暴露", "当前田面明水状态", STANDING_WATER_LABELS[standing_status]),
        ("环境条件", "日平均温度", "缺失" if temperature_c is None else f"{temperature_c:g}℃"),
        ("环境条件", "平均相对湿度", "缺失" if humidity_pct is None else f"{humidity_pct:g}%"),
        ("作业条件", "排水时间", "缺失" if drainage_delay_hours is None else f"{drainage_delay_hours:g}小时"),
        ("作业条件", "预计作业风速", "缺失" if wind_speed_ms is None else f"{wind_speed_ms:g}m/s"),
        ("病害状态", "目标病害", DISEASE_LABELS.get(target_disease, "缺失")),
        ("病害状态", "当前症状", SYMPTOM_LABELS.get(symptom_status, "缺失")),
        ("病害状态", "诊断状态", DIAGNOSIS_LABELS[diagnosis_status]),
        ("病害状态", "洪涝前病情基线", BASELINE_LABELS[pre_flood_baseline]),
        ("病害状态", "品种身份", CULTIVAR_LABELS[cultivar_name]),
        ("病害状态", "周边病害压力", PRESSURE_LABELS[disease_pressure]),
    ]
    st.dataframe(
        pd.DataFrame(submitted_rows, columns=["类别", "字段", "已提交值"]),
        hide_index=True,
        width="stretch",
        height=500,
    )
    st.markdown("**当前可判断**")
    for item in result.known_evidence:
        st.write(f"- {item}")
    st.markdown("**当前不能判断**")
    for item in result.unknown_evidence:
        st.write(f"- {item}")

st.page_link("pages/3_intervention.py", label="查看完整干预窗口分析", icon="⏱")
