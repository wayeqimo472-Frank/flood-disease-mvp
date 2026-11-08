import pandas as pd
import streamlit as st

from risk_engine import load_priors, load_rules
from ui_common import (
    GAP_PATH,
    PARAMETER_ROLE_LABELS,
    current_source_label,
    has_current_state,
    render_assessment_status,
)


st.title("参数与科研依据")
render_assessment_status()
if not has_current_state():
    st.info("当前会话尚未提交风险情景。通用模型限制和数据缺口仍可在本页查看。")
result = st.session_state.get("current_result")
st.caption(f"当前查看：{current_source_label()}")
st.info("本页集中展示判断依据、证据来源、实际使用参数和模型限制。")

basis_tab, parameter_tab, rule_tab, gap_tab = st.tabs(
    ["判断依据", "模型参数", "决策规则", "数据缺口"]
)

with basis_tab:
    if result is None:
        st.write("尚未提交风险情景，因此暂无本次判断依据。")
        with st.expander("模型限制与后续校准", expanded=True):
            st.write("- 当前页面不代表任何具体田块已经发病或减产。")
            st.write("- 先提交风险情景后，才能查看本次实际使用的参数。")
    else:
        for reason in result.rationale:
            st.write(f"- {reason}")
        st.write("**处置优先级不是病害发生概率，也不等于实际产量损失。**")
        st.write("**本页不自动提供农药名称、剂量或处方。**")
        with st.expander("模型限制与后续校准", expanded=True):
            for limitation in result.limitations:
                st.write(f"- {limitation}")

priors = pd.DataFrame(load_priors().values())
rules = pd.DataFrame(load_rules().values())
usage = pd.DataFrame(
    [
        {
            "parameter_id": item.parameter_id,
            "用途类别": PARAMETER_ROLE_LABELS[item.role],
            "实际使用字段": item.field,
            "用途说明": item.detail,
        }
        for item in (result.parameter_uses if result is not None else ())
    ],
    columns=["parameter_id", "用途类别", "实际使用字段", "用途说明"],
)
used_priors = usage.merge(priors, on="parameter_id", how="left")
used_rules = (
    rules[rules["rule_id"].isin(result.evidence_rule_ids)]
    if result is not None
    else rules.iloc[0:0]
)

with parameter_tab:
    if result is None:
        st.info("提交风险情景后，此处将显示本次实际读取的参数。")
    else:
        st.caption(
            "P013的4天边界用于状态分支，25%减产上界仅作解释，不进入风险分数。"
            "E14当前没有独立区域遥感像元输入，不使用田块明水天数替代。"
        )
        st.dataframe(
            used_priors[
                [
                    "parameter_id",
                    "用途类别",
                    "实际使用字段",
                    "用途说明",
                    "metric",
                    "time_value",
                    "time_unit",
                    "value_low",
                    "value_central",
                    "value_high",
                    "unit",
                    "source_id",
                    "evidence_level",
                    "verification_status",
                    "allowed_use",
                    "prohibited_use",
                ]
            ],
            hide_index=True,
            width="stretch",
            height=360,
        )

with rule_tab:
    if result is None:
        st.info("提交风险情景后，此处将显示本次实际使用的决策规则。")
    else:
        st.dataframe(
            used_rules[
                [
                    "rule_id",
                    "category",
                    "metric",
                    "value_low",
                    "value_central",
                    "value_high",
                    "unit",
                    "evidence_level",
                    "source_id",
                ]
            ],
            hide_index=True,
            width="stretch",
            height=320,
        )

with gap_tab:
    gap_data = pd.read_csv(GAP_PATH)
    st.dataframe(
        gap_data[
            [
                "gap_item",
                "availability",
                "best_available_data",
                "evidence_level",
                "current_use_in_app",
                "next_action",
            ]
        ].rename(
            columns={
                "gap_item": "缺口",
                "availability": "可得性",
                "best_available_data": "目前可用证据",
                "evidence_level": "等级",
                "current_use_in_app": "页面当前用法",
                "next_action": "下一步",
            }
        ),
        hide_index=True,
        width="stretch",
        height=360,
    )
