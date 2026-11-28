import pandas as pd
import streamlit as st

from robustness import UncertaintyBounds, analyze_robustness
from simulation_evidence import load_summary
from ui_components import page_header, render_window_cards
from ui_common import (
    CASE_NAME,
    DATA_COMPLETENESS_LABELS,
    WINDOW_STATUS_LABELS,
    current_source_label,
    has_current_state,
    render_assessment_status,
    render_metric_cards,
    render_priority_notice,
    render_safety_notices,
    scenario_from_inputs,
)


page_header(
    "干预窗口分析",
    "围绕排水、巡查、诊断和防治四个动作，查看当前情景下的时间与安全边界。",
    meta=[CASE_NAME, "当前已提交情景"],
)
render_assessment_status()
if not has_current_state():
    st.info("请先提交一次风险情景，再查看对应干预窗口。")
    st.page_link(
        "pages/2_risk.py",
        label="进入风险情景筛查",
        icon=":material/monitoring:",
    )
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

st.subheader("四段干预窗口")
render_window_cards(
    [
        {
            "window": item.window,
            "status": WINDOW_STATUS_LABELS.get(item.status, item.status),
            "action": item.action,
            "evidence": item.evidence,
        }
        for item in result.windows
    ]
)
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
with st.expander("查看可排序明细表", expanded=False):
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

st.subheader("不确定性区间与决策稳健性分析")
st.caption(
    "针对公开遥感重访周期和再分析气象网格平滑误差，对当前输入施加对称扰动区间，"
    "识别哪些处置窗口在误差范围内保持不变（零现场数据也能放心执行），哪些窗口会翻转（必须优先核查）。"
)
bound_cols = st.columns(5)
flood_days_delta = bound_cols[0].slider(
    "明水天数误差 ±天",
    min_value=0.0,
    max_value=5.0,
    value=2.0,
    step=0.5,
)
drainage_delay_delta = bound_cols[1].slider(
    "排水延迟误差 ±h",
    min_value=0.0,
    max_value=48.0,
    value=24.0,
    step=6.0,
)
temperature_delta = bound_cols[2].slider(
    "日均温误差 ±℃",
    min_value=0.0,
    max_value=5.0,
    value=2.0,
    step=0.5,
)
humidity_delta = bound_cols[3].slider(
    "相对湿度误差 ±%",
    min_value=0.0,
    max_value=20.0,
    value=10.0,
    step=2.0,
)
wind_delta = bound_cols[4].slider(
    "作业风速误差 ±m/s",
    min_value=0.0,
    max_value=3.0,
    value=1.0,
    step=0.5,
)

base_scenario = scenario_from_inputs(inputs)
bounds = UncertaintyBounds(
    flood_days_delta=flood_days_delta,
    drainage_delay_delta_hours=drainage_delay_delta,
    temperature_delta_c=temperature_delta,
    humidity_delta_pct=humidity_delta,
    wind_delta_ms=wind_delta,
)
robustness_report = analyze_robustness(base_scenario, bounds)
rob_metrics = st.columns(3)
rob_metrics[0].metric("联合扰动情景数", f"{robustness_report.total_scenarios} 个")
rob_metrics[1].metric(
    "处置优先级一致率",
    f"{robustness_report.risk_agreement_pct:.1f}%",
)
rob_metrics[2].metric(
    "完全稳健窗口数",
    f"{robustness_report.invariant_window_count} / {len(robustness_report.window_results)}",
)

rob_rows = []
for w in robustness_report.window_results:
    rob_rows.append(
        {
            "窗口": w.window,
            "基准状态": WINDOW_STATUS_LABELS.get(w.base_status, w.base_status),
            "区间一致率": f"{w.base_agreement_pct:.1f}%",
            "稳健等级": w.stability_tier,
            "敏感驱动因子": "、".join(w.sensitive_drivers) if w.sensitive_drivers else "无（区间内不敏感）",
            "区间内出现状态": " / ".join(
                WINDOW_STATUS_LABELS.get(s, s) for s in w.observed_statuses
            ),
        }
    )
st.dataframe(pd.DataFrame(rob_rows), hide_index=True, width="stretch")

rob_left, rob_right = st.columns(2, gap="large")
with rob_left:
    st.markdown("**可跨误差稳健执行（无需等实测即可先做）**")
    if robustness_report.invariant_actions:
        for item in robustness_report.invariant_actions:
            st.write(f"- {item}")
    else:
        st.write("- 当前参数处于阈值敏感区，建议结合右栏优先核查后再做绝对定论。")
with rob_right:
    st.markdown("**优先田间核查（决定窗口是否翻转）**")
    if robustness_report.priority_verifications:
        for item in robustness_report.priority_verifications:
            st.write(f"- {item}")
    else:
        st.write("- 当前误差区间内各窗口均未发生状态翻转。")

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
