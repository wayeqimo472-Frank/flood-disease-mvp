import pandas as pd
import streamlit as st

from storage import list_assessment_runs
from ui_common import (
    CASE_CONFIG,
    DATA_COMPLETENESS_LABELS,
    ENVIRONMENT_METRIC_LABELS,
    current_source_label,
    has_current_state,
    render_assessment_status,
    render_metric_cards,
)


st.title("项目总览")
st.caption("多区域案例 · 涝渍暴露 · 作物状态 · 病害证据 · 干预窗口")
st.info(
    "系统依据已提交的涝渍暴露、作物状态和病害证据生成情景筛查结果，"
    "并说明缺失数据带来的判断限制。"
)
render_assessment_status()

st.subheader("最近一次计算摘要")
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
    st.caption(f"情景来源：{current_source_label()}")
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

st.subheader("主要功能")
col_1, col_2, col_3, col_4 = st.columns(4, gap="large")
with col_1:
    st.markdown("**风险情景筛查**")
    st.write("录入涝渍暴露、病害证据和环境条件，生成当前筛查摘要。")
    st.page_link("pages/2_risk.py", label="进入风险筛查", icon="🌽")
with col_2:
    st.markdown("**干预窗口分析**")
    st.write("查看排水、巡查、诊断和防治四段窗口及安全限制。")
    st.page_link("pages/3_intervention.py", label="查看干预窗口", icon="⏱")
with col_3:
    st.markdown("**田块数据管理**")
    st.write("下载模板、校验并批量计算田块观测记录。")
    st.page_link("pages/4_field_data.py", label="管理田块数据", icon="📁")
with col_4:
    st.markdown("**数据拼接**")
    st.write("查看公开案例、ICASA 映射、田块几何和 SAR 指标接口。")
    st.page_link("pages/6_integration.py", label="查看拼接层", icon="🛰")

st.subheader("当前数据边界")
for limitation in CASE_CONFIG.get("overview_limits", []):
    st.write(f"- {limitation}")

recent_runs = list_assessment_runs(limit=5)
if recent_runs:
    st.subheader("本地计算历史")
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
