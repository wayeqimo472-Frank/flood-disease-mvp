import streamlit as st

from ui_common import (
    DATA_COMPLETENESS_LABELS,
    ENVIRONMENT_METRIC_LABELS,
    current_source_label,
    has_current_state,
    render_assessment_status,
    render_metric_cards,
)


st.title("项目总览")
st.caption("洪涝暴露 → 作物抗逆性下降 → 病害风险 → 干预窗口 → 减损决策")
st.info(
    "本系统是证据约束下的情景筛查与辅助决策原型，"
    "不是病害概率预测器，也不输出精确产量损失。"
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

st.subheader("系统工作范围")
col_1, col_2, col_3 = st.columns(3, gap="large")
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

st.subheader("当前数据边界")
st.write(
    "- 已接入公开真实淹水田—未淹对照时序，但该数据没有病害终点。"
    "\n- 已接入涝渍存活和病害时间进展的先验数据，不能把它们拼成因果系数。"
    "\n- 尚未获得本地区真实受淹田与未受淹对照田的配对观测。"
    "\n- 温度和湿度缺失时，不推断环境适宜度。"
    "\n- E14区域遥感分类需要独立像元数据，当前保持不可用。"
    "\n- 所有预设值都是情景假设，不是田间实测。"
)
st.page_link(
    "pages/5_evidence.py",
    label="查看已接入的公开案例与来源",
    icon="📚",
)
