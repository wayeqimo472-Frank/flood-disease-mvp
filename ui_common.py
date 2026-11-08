from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from risk_engine import FieldScenario


GAP_PATH = Path(__file__).resolve().parent / "data" / "gap_availability_v0.1.csv"
DEFAULT_PRESET = "V6 严重淹水 / 高压力"

SCENARIO_PRESETS = {
    "短时淹水 / 及时排水": {
        "crop_stage": "V3",
        "flood_days": 2.0,
        "waterlog_days": 0.0,
        "drainage_delay_hours": 12.0,
        "standing_water": False,
        "target_disease": "southern_rust",
        "symptom_status": "none",
        "diagnosis_status": "not_assessed",
        "pre_flood_baseline": "unknown",
        "cultivar_name": "unknown",
        "disease_pressure": "moderate",
        "temperature_c": 26.0,
        "humidity_pct": 85.0,
        "wind_speed_ms": 2.0,
    },
    "V6 严重淹水 / 高压力": {
        "crop_stage": "V6",
        "flood_days": 5.0,
        "waterlog_days": 3.0,
        "drainage_delay_hours": 48.0,
        "standing_water": False,
        "target_disease": "southern_rust",
        "symptom_status": "none",
        "diagnosis_status": "not_assessed",
        "pre_flood_baseline": "unknown",
        "cultivar_name": "unknown",
        "disease_pressure": "high",
        "temperature_c": 27.0,
        "humidity_pct": 95.0,
        "wind_speed_ms": 2.0,
    },
    "长时淹水 / 零星症状": {
        "crop_stage": "V3",
        "flood_days": 10.0,
        "waterlog_days": 7.0,
        "drainage_delay_hours": 96.0,
        "standing_water": False,
        "target_disease": "southern_rust",
        "symptom_status": "sparse",
        "diagnosis_status": "suspected",
        "pre_flood_baseline": "sporadic",
        "cultivar_name": "unknown",
        "disease_pressure": "high",
        "temperature_c": 27.0,
        "humidity_pct": 95.0,
        "wind_speed_ms": 2.5,
    },
    "灌浆期 / 已确诊真菌病害": {
        "crop_stage": "R3",
        "flood_days": 10.0,
        "waterlog_days": 5.0,
        "drainage_delay_hours": 8.0,
        "standing_water": False,
        "target_disease": "southern_rust",
        "symptom_status": "obvious",
        "diagnosis_status": "confirmed_fungal",
        "pre_flood_baseline": "sporadic",
        "cultivar_name": "郑单958",
        "disease_pressure": "high",
        "temperature_c": 28.0,
        "humidity_pct": 90.0,
        "wind_speed_ms": 2.0,
    },
}

CUSTOM_SCENARIO = {
    "crop_stage": None,
    "flood_days": None,
    "waterlog_days": None,
    "drainage_delay_hours": None,
    "standing_water": None,
    "target_disease": None,
    "symptom_status": None,
    "diagnosis_status": "not_assessed",
    "pre_flood_baseline": "unknown",
    "cultivar_name": "unknown",
    "disease_pressure": "unknown",
    "temperature_c": None,
    "humidity_pct": None,
    "wind_speed_ms": None,
}

INPUT_FIELDS = tuple(CUSTOM_SCENARIO)

STAGE_LABELS = {
    "V3": "V3 苗期",
    "V6": "V6 拔节期",
    "VT": "VT 抽雄期",
    "R3": "R3 灌浆期",
}
DISEASE_LABELS = {
    "southern_rust": "玉米南方锈病（可参数化）",
    "stem_rot": "茎基腐病（仅监测/诊断）",
    "leaf_spot": "小斑/弯孢叶斑类（仅监测）",
    "ear_rot": "穗腐病（后期监测）",
}
SYMPTOM_LABELS = {
    "none": "尚未发现症状",
    "sparse": "零星病叶或异常",
    "obvious": "症状已经明显",
}
DIAGNOSIS_LABELS = {
    "not_assessed": "尚未诊断",
    "suspected": "疑似，但未确诊",
    "confirmed_fungal": "已确认真菌性病害",
    "confirmed_nonfungal": "已排除真菌性病害",
}
BASELINE_LABELS = {
    "unknown": "未知（不使用区域值代替）",
    "none": "洪涝前未见病害",
    "sporadic": "洪涝前零星发生",
    "established": "洪涝前已经普遍发生",
}
CULTIVAR_LABELS = {
    "unknown": "未知",
    "other": "其他品种",
    "MY73": "MY73",
    "秋乐368": "秋乐368",
    "现代959": "现代959",
    "京科938": "京科938",
    "郑单958": "郑单958（有公开耐涝对比）",
    "泛玉298": "泛玉298",
    "棒博士767": "棒博士767",
    "伟科702": "伟科702",
    "科腾918": "科腾918",
    "鼎诺212": "鼎诺212",
    "伟科812": "伟科812",
    "浚单1618": "浚单1618",
}
PRESSURE_LABELS = {"low": "低", "moderate": "中", "high": "高", "unknown": "未知"}
FLOOD_CLASS_LABELS = {"not_available": "暂无独立遥感像元数据"}
ENVIRONMENT_LABELS = {
    "optimal": "适宜：24—28℃且RH≥90%",
    "favorable": "可能适宜：15—31℃且高湿",
    "partial": "仅部分条件满足",
    "unfavorable": "当前环境不利",
    "not_modeled": "所选病害未做环境建模",
    "not_applicable": "已排除真菌病害",
    "insufficient_data": "数据不足：缺少温度或湿度",
}
ENVIRONMENT_METRIC_LABELS = {
    "optimal": "适宜",
    "favorable": "可能适宜",
    "partial": "部分满足",
    "unfavorable": "不利",
    "not_modeled": "未建模",
    "not_applicable": "不适用",
    "insufficient_data": "数据不足",
}
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
STANDING_WATER_LABELS = {
    "unknown": "未知",
    "yes": "是，当前仍有明水",
    "no": "否，当前无明水",
}
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


def clone_inputs(values: dict[str, object]) -> dict[str, object]:
    return {field: values.get(field) for field in INPUT_FIELDS}


def scenario_from_inputs(values: dict[str, object]) -> FieldScenario:
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
    )


def save_current_state(
    preset_name: str,
    inputs: dict[str, object],
    result,
    modified_fields: list[str],
) -> None:
    st.session_state.current_preset = preset_name
    st.session_state.current_inputs = clone_inputs(inputs)
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
    if result.risk_low == "unknown":
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
