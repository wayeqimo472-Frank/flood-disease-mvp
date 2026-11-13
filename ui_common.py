from __future__ import annotations

import sqlite3
from html import escape
from pathlib import Path

import streamlit as st

from case_pack import DEFAULT_CASE_ID, get_case_pack
from risk_engine import FieldScenario
from storage import save_assessment_run


CASE_PACK = get_case_pack(DEFAULT_CASE_ID)
CASE_CONFIG = CASE_PACK.config
CASE_NAME = CASE_PACK.name
CROP_NAME = CASE_PACK.crop_name
GAP_PATH = CASE_PACK.data_file("gaps")
PUBLIC_DATA_REGISTER_PATH = (
    Path(__file__).resolve().parent / "data" / "public_dataset_register_v0.2.csv"
)
PUBLIC_GAP_MATRIX_PATH = (
    Path(__file__).resolve().parent / "data" / "public_data_gap_matrix_v0.2.csv"
)
PUBLIC_ALL_MISSING_PATH = (
    Path(__file__).resolve().parent / "data" / "all_missing_data_v0.3.csv"
)
LWD_PROXY_SUMMARY_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "public_evidence_v0.2"
    / "lwd_rh90_proxy_summary.csv"
)
ONE_ACRE_OVERALL_SUMMARY_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "public_evidence_v0.2"
    / "one_acre_overall_exposure_summary.csv"
)
DEFAULT_PRESET = CASE_CONFIG["default_preset"]
SCENARIO_PRESETS = CASE_CONFIG["scenario_presets"]
CUSTOM_SCENARIO = CASE_CONFIG["custom_scenario"]

INPUT_FIELDS = tuple(CUSTOM_SCENARIO)

STAGE_LABELS = CASE_CONFIG["stages"]
DISEASE_LABELS = {
    key: value["label"] for key, value in CASE_CONFIG["diseases"].items()
}
CULTIVAR_LABELS = {
    key: value["label"] for key, value in CASE_CONFIG["cultivars"].items()
}
CULTIVAR_NOTES = {
    key: value["note"]
    for key, value in CASE_CONFIG["cultivars"].items()
    if value.get("note")
}
SYMPTOM_LABELS = CASE_CONFIG["labels"]["symptom"]
DIAGNOSIS_LABELS = CASE_CONFIG["labels"]["diagnosis"]
BASELINE_LABELS = CASE_CONFIG["labels"]["baseline"]
PRESSURE_LABELS = CASE_CONFIG["labels"]["pressure"]
FLOOD_CLASS_LABELS = CASE_CONFIG["labels"]["flood_class"]
ENVIRONMENT_LABELS = CASE_CONFIG["labels"]["environment"]
ENVIRONMENT_METRIC_LABELS = CASE_CONFIG["labels"]["environment_metric"]
DATA_COMPLETENESS_LABELS = {
    "complete": "完整",
    "partial": "部分缺失",
    "insufficient_core": "核心暴露缺失",
}
PARAMETER_ROLE_LABELS = {
    "定量计算参数": "定量计算参数",
    "状态判断参数": "状态判断参数",
    "解释性证据": "解释性证据",
}
STANDING_WATER_LABELS = CASE_CONFIG["labels"]["standing_water"]
WINDOW_STATUS_LABELS = {
    "not_applicable": "不适用",
    "active": "立即排水",
    "waterlogging_management": "转排渍散墒",
    "open": "窗口开启",
    "closing": "窗口收窄",
    "delayed": "已延迟",
    "blocked_safety": "安全限制",
    "scheduled": "按计划执行",
    "completed_fungal": "已确认真菌性",
    "completed_nonfungal": "已排除真菌性",
    "standby": "待触发",
    "required": "必须诊断",
    "diagnosis_only": "仅监测诊断",
    "harvest_monitoring": "后期巡查管理",
    "blocked_water": "积水限制",
    "blocked_weather": "气象限制",
    "data_insufficient": "数据不足",
    "condition_unknown": "作业条件未知",
    "no_fungicide": "禁用杀菌剂方案",
    "prepare_early": "提前准备",
    "monitor": "持续监测",
    "pending_diagnosis": "等待诊断",
    "consult_only": "仅咨询当地植保",
}


def activate_case(case_id: str) -> None:
    global CASE_PACK, CASE_CONFIG, CASE_NAME, CROP_NAME
    global GAP_PATH, DEFAULT_PRESET, SCENARIO_PRESETS, CUSTOM_SCENARIO
    global INPUT_FIELDS, STAGE_LABELS, DISEASE_LABELS, CULTIVAR_LABELS
    global CULTIVAR_NOTES, SYMPTOM_LABELS, DIAGNOSIS_LABELS, BASELINE_LABELS
    global PRESSURE_LABELS, FLOOD_CLASS_LABELS, ENVIRONMENT_LABELS
    global ENVIRONMENT_METRIC_LABELS, STANDING_WATER_LABELS

    pack = get_case_pack(case_id)
    previous = st.session_state.get("_active_case_id")
    if previous and previous != case_id:
        for key in (
            "current_result",
            "current_inputs",
            "current_preset",
            "current_modified_fields",
            "current_case_id",
            "storage_error",
            "risk_preset",
        ):
            st.session_state.pop(key, None)

    CASE_PACK = pack
    CASE_CONFIG = pack.config
    CASE_NAME = pack.name
    CROP_NAME = pack.crop_name
    GAP_PATH = pack.data_file("gaps")
    DEFAULT_PRESET = CASE_CONFIG["default_preset"]
    SCENARIO_PRESETS = CASE_CONFIG["scenario_presets"]
    CUSTOM_SCENARIO = CASE_CONFIG["custom_scenario"]
    INPUT_FIELDS = tuple(CUSTOM_SCENARIO)
    STAGE_LABELS = CASE_CONFIG["stages"]
    DISEASE_LABELS = {
        key: value["label"] for key, value in CASE_CONFIG["diseases"].items()
    }
    CULTIVAR_LABELS = {
        key: value["label"] for key, value in CASE_CONFIG["cultivars"].items()
    }
    CULTIVAR_NOTES = {
        key: value["note"]
        for key, value in CASE_CONFIG["cultivars"].items()
        if value.get("note")
    }
    SYMPTOM_LABELS = CASE_CONFIG["labels"]["symptom"]
    DIAGNOSIS_LABELS = CASE_CONFIG["labels"]["diagnosis"]
    BASELINE_LABELS = CASE_CONFIG["labels"]["baseline"]
    PRESSURE_LABELS = CASE_CONFIG["labels"]["pressure"]
    FLOOD_CLASS_LABELS = CASE_CONFIG["labels"]["flood_class"]
    ENVIRONMENT_LABELS = CASE_CONFIG["labels"]["environment"]
    ENVIRONMENT_METRIC_LABELS = CASE_CONFIG["labels"]["environment_metric"]
    STANDING_WATER_LABELS = CASE_CONFIG["labels"]["standing_water"]
    st.session_state._active_case_id = case_id


def clone_inputs(values: dict[str, object]) -> dict[str, object]:
    return {field: values.get(field) for field in INPUT_FIELDS}


def scenario_from_inputs(
    values: dict[str, object],
    case_id: str | None = None,
) -> FieldScenario:
    active_case_id = case_id or st.session_state.get(
        "_active_case_id",
        DEFAULT_CASE_ID,
    )
    return FieldScenario(
        crop_stage=values["crop_stage"],
        flood_days=values["flood_days"],
        waterlog_days=values["waterlog_days"],
        drainage_delay_hours=values["drainage_delay_hours"],
        standing_water=values["standing_water"],
        target_disease=values["target_disease"],
        symptom_status=values["symptom_status"],
        diagnosis_status=values["diagnosis_status"],
        pre_flood_baseline=values["pre_flood_baseline"],
        cultivar_name=values["cultivar_name"],
        disease_pressure=values["disease_pressure"],
        temperature_c=values["temperature_c"],
        humidity_pct=values["humidity_pct"],
        wind_speed_ms=values["wind_speed_ms"],
        case_id=active_case_id,
    )


def save_current_state(
    preset_name: str,
    inputs: dict[str, object],
    result,
    modified_fields: list[str],
) -> None:
    case_id = result.case_id
    inputs_to_save = clone_inputs(inputs)
    try:
        save_assessment_run(
            case_id=case_id,
            case_version=result.case_version,
            inputs=inputs_to_save,
            result=result,
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        st.session_state.storage_error = str(error)
    else:
        st.session_state.pop("storage_error", None)
    st.session_state.current_case_id = case_id
    st.session_state.current_preset = preset_name
    st.session_state.current_inputs = inputs_to_save
    st.session_state.current_result = result
    st.session_state.current_modified_fields = tuple(modified_fields)


def current_source_label() -> str:
    if "current_result" not in st.session_state:
        return "暂无评估记录"
    preset_name = st.session_state.current_preset
    modified = st.session_state.current_modified_fields
    if preset_name == "自定义":
        return "自定义情景"
    if modified:
        return f"{preset_name}（参数已修改）"
    return f"{preset_name}（情景假设值，非田间实测）"


def has_current_state() -> bool:
    return "current_result" in st.session_state


def render_assessment_status() -> None:
    st.markdown(
        """
        <style>
        .status-pill {
            display: inline-block;
            padding: 0.2rem 0.65rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            background: #e8f5e9;
            color: #1b5e20;
        }
        .status-pill.empty {
            background: #f1f3f4;
            color: #5f6368;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        title_col, badge_col = st.columns([4, 1])
        title_col.markdown("**当前评估状态**")
        if not has_current_state():
            badge_col.markdown(
                '<div class="status-pill empty">暂无记录</div>',
                unsafe_allow_html=True,
            )
            st.caption("当前会话尚未提交风险情景。请先进入“风险情景筛查”。")
            return

        badge_col.markdown(
            '<div class="status-pill">已提交计算</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"当前情景：{current_source_label()}")
        metric_cols = st.columns(3)
        metric_cols[0].caption("输入状态")
        metric_cols[0].write("已提交")
        metric_cols[1].caption("数据完整性")
        metric_cols[1].write(
            DATA_COMPLETENESS_LABELS[st.session_state.current_result.data_completeness]
        )
        metric_cols[2].caption("结果来源")
        metric_cols[2].write("当前已提交输入")
    if st.session_state.get("storage_error"):
        st.warning(f"计算已完成，但写入本地数据库失败：{st.session_state.storage_error}")


def result_cards(result) -> list[tuple[str, str]]:
    return [
        ("数据完整性", DATA_COMPLETENESS_LABELS[result.data_completeness]),
        ("处置优先级", result.risk_label),
        ("田间证据", result.field_evidence_status),
        ("环境适宜度", ENVIRONMENT_METRIC_LABELS[result.environment_suitability]),
    ]


def render_metric_cards(cards: list[tuple[str, str]]) -> None:
    cards_html = "".join(
        (
            '<div class="result-metric">'
            f'<div class="result-metric-label">{escape(label)}</div>'
            f'<div class="result-metric-value">{escape(str(value))}</div>'
            "</div>"
        )
        for label, value in cards
    )
    st.markdown(
        f"""
        <style>
        .result-metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 0.75rem 1rem;
            margin: 0.2rem 0 0.8rem;
        }}
        .result-metric {{
            min-width: 0;
            padding: 0.15rem 0.3rem 0.4rem 0;
        }}
        .result-metric-label {{
            margin-bottom: 0.35rem;
            font-size: 0.875rem;
            line-height: 1.4;
            opacity: 0.72;
        }}
        .result-metric-value {{
            font-size: clamp(1.3rem, 2.2vw, 1.75rem);
            font-weight: 600;
            line-height: 1.22;
            white-space: normal;
            overflow: visible;
            overflow-wrap: anywhere;
            text-overflow: clip;
        }}
        @media (max-width: 700px) {{
            .result-metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        }}
        </style>
        <div class="result-metrics">{cards_html}</div>
        """,
        unsafe_allow_html=True,
    )


def render_priority_notice(result) -> None:
    if result.risk_model == "monitoring_only":
        st.info(
            f"当前案例为“{result.risk_label}”：系统保留暴露、病害和产量观测，"
            "但不把外部文献先验包装成本地区定量风险。"
        )
    elif result.risk_low == "unknown":
        st.warning(
            f"当前处置优先级为“{result.risk_label}”：核心涝渍暴露数据不完整，"
            "未把缺失值当作0或低风险。"
        )
    elif result.risk_high in {"high", "very_high"}:
        st.warning(
            f"当前处置优先级为“{result.risk_label}”，应优先完成排水、巡查和诊断。"
            "这表示管理上需要先处理，不代表田间已经发病、病害概率高或已经减产。"
        )
    elif result.risk_high == "moderate":
        st.info(f"当前处置优先级为“{result.risk_label}”，重点是降湿、巡田和环境监测。")
    else:
        st.success(f"当前处置优先级为“{result.risk_label}”，仍应按计划巡查并记录田间证据。")


def render_safety_notices(result) -> None:
    if any(item.status == "pending_diagnosis" for item in result.windows):
        st.error("已出现疑似症状但尚未确诊：先取样诊断，禁止直接依据风险等级用药。")
    if result.field_evidence_status == "已排除真菌性病害":
        st.error("已完成真菌排除：不得沿用真菌性病害防治路径或推荐杀菌剂。")
    if any(item.status == "data_insufficient" for item in result.windows):
        st.warning("部分决策窗口因输入缺失而无法判断，缺失值未被当作0或安全条件。")
    if any(
        item.status in {"blocked_water", "blocked_weather", "blocked_safety"}
        for item in result.windows
    ):
        st.warning("当前存在田间或气象作业限制，先满足安全条件再考虑防治。")
