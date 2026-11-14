import pandas as pd
import streamlit as st

from simulation_evidence import load_summary
from ui_common import (
    DATA_COMPLETENESS_LABELS,
    WINDOW_STATUS_LABELS,
    current_source_label,
    has_current_state,
    render_assessment_status,
    render_metric_cards,
    render_priority_notice,
    render_safety_notices,
)


st.title("干预窗口分析")
render_assessment_status()
if not has_current_state():
    st.info("请先提交一次风险情景，再查看对应干预窗口。")
    st.page_link("pages/2_risk.py", label="进入风险情景筛查", icon="🌽")
    st.stop()

result = st.session_state.current_result
inputs = st.session_state.current_inputs
flood_value = "缺失" if inputs["flood_days"] is None else f"{inputs['flood_days']:g}天"
waterlog_value = (
    "缺失" if inputs["waterlog_days"] is None else f"{inputs['waterlog_days']:g}天"
)
st.caption(f"当前使用：{current_source_label()}")
st.caption(f"明水{flood_value}，渍水{waterlog_value}。")

render_metric_cards(
    [
        ("数据完整性", DATA_COMPLETENESS_LABELS[result.data_completeness]),
        ("处置优先级", result.risk_label),
        ("诊断状态", result.field_evidence_status),
    ]
)
render_priority_notice(result)
render_safety_notices(result)

windows_df = pd.DataFrame(
    [
        {
            "窗口": item.window,
            "状态": WINDOW_STATUS_LABELS.get(item.status, item.status),
            "建议动作": item.action,
            "证据": item.evidence,
        }
        for item in result.windows
    ]
)
st.subheader("四段干预窗口")
st.dataframe(windows_df, hide_index=True, width="stretch")
st.write(f"**当前病害处置窗口：** {result.disease_window.split(': ', 1)[1]}")
st.write(f"**巡查计划：** {result.monitoring_plan}")
st.caption(f"病害窗口的精确天数：{result.disease_window_precise_days}")

with st.expander("APSIM 排水时限参考（模型仿真，非本地预测）", expanded=False):
    simulation = load_summary()
    reference = simulation[
        [
            "timing",
            "drainage_hold_days",
            "ponding_days",
            "simulated_yield_kg_ha",
            "observed_yield_kg_ha",
            "simulated_yield_relative_to_control_pct",
        ]
    ].rename(
        columns={
            "timing": "淹水阶段",
            "drainage_hold_days": "关闭排水并补水天数",
            "ponding_days": "模拟积水天数",
            "simulated_yield_kg_ha": "模拟产量kg/ha",
            "observed_yield_kg_ha": "验证试验观测kg/ha",
            "simulated_yield_relative_to_control_pct": "模拟产量较对照%",
        }
    )
    st.warning(
        "这组结果来自APSIM官方验证情景，只用于提示排水延误的敏感性，"
        "不自动替换当前田块输入，也不计算河南本地产量损失。"
    )
    st.dataframe(reference, hide_index=True, width="stretch")
    st.write(
        "- 4天处理：早期和后期模拟产量分别较对照下降约28.5%和28.8%。"
    )
    st.write(
        "- 8天处理：早期和后期模拟产量分别较对照下降约47.0%和45.8%。"
    )
    st.caption(
        "因此，当前决策仍以尽快排水为优先；上述百分比只属于验证情景的模型结果。"
    )

st.subheader("判断边界")
known_col, unknown_col = st.columns(2, gap="large")
with known_col:
    st.markdown("**当前可判断**")
    for item in result.known_evidence:
        st.write(f"- {item}")
with unknown_col:
    st.markdown("**当前不能判断**")
    for item in result.unknown_evidence:
        st.write(f"- {item}")

st.caption(result.stage_disease_note)
