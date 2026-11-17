import pandas as pd
import streamlit as st

from storage import list_assessment_runs
from ui_common import (
    CASE_CONFIG,
    CASE_NAME,
    DATA_COMPLETENESS_LABELS,
    ENVIRONMENT_METRIC_LABELS,
    current_source_label,
    has_current_state,
    render_assessment_status,
    render_metric_cards,
)
from ui_components import (
    page_header,
    render_boundary_module,
    render_overview_hero,
    render_quick_routes,
    section_header,
)


page_header(
    "项目总览",
    "从涝渍暴露、作物状态到病害证据与干预窗口，保留每一步判断的边界。",
    meta=[CASE_NAME, "单用户本地决策台"],
)

if has_current_state():
    result = st.session_state.current_result
    inputs = st.session_state.current_inputs
    flood_value = (
        "缺失" if inputs["flood_days"] is None else f"{inputs['flood_days']:g}天"
    )
    waterlog_value = (
        "缺失"
        if inputs["waterlog_days"] is None
        else f"{inputs['waterlog_days']:g}天"
    )
    source_label = current_source_label()
    risk_label = result.risk_label
else:
    result = None
    source_label = "当前会话暂无提交"
    risk_label = "等待评估"
    flood_value = "缺失"
    waterlog_value = "缺失"

render_overview_hero(
    has_result=result is not None,
    source_label=source_label,
    risk_label=risk_label,
    flood_value=flood_value,
    waterlog_value=waterlog_value,
)

render_assessment_status()

section_header("最近一次计算摘要", "只看当前已经提交的输入，不把缺失值当作零。")
if result is not None:
    st.caption(f"情景来源：{source_label}")
    render_metric_cards(
        [
            ("数据完整性", DATA_COMPLETENESS_LABELS[result.data_completeness]),
            ("处置优先级", result.risk_label),
            ("田间证据", result.field_evidence_status),
            ("环境适宜度", ENVIRONMENT_METRIC_LABELS[result.environment_suitability]),
        ]
    )
    st.write(f"- 明水：{flood_value}")
    st.write(f"- 渍水：{waterlog_value}")
else:
    st.caption("暂无记录：当前会话还没有提交过风险情景。")

section_header("进入工作流", "四个入口对应从判断到数据、证据的完整路径。")
render_quick_routes()

section_header("当前数据边界", "这些限制会随结果一起保留。")
render_boundary_module(CASE_CONFIG.get("overview_limits", []))

recent_runs = list_assessment_runs(limit=5)
if recent_runs:
    section_header("本地计算历史", "最近的提交记录保存在当前本地数据库中。")
    st.dataframe(
        pd.DataFrame(recent_runs).rename(
            columns={
                "run_hash": "记录哈希",
                "case_id": "案例包",
                "case_version": "版本",
                "created_at": "计算时间",
            }
        ),
        hide_index=True,
        width="stretch",
    )
