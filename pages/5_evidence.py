import pandas as pd
import streamlit as st

from risk_engine import load_priors, load_rules
from ui_common import (
    CASE_CONFIG,
    CASE_NAME,
    GAP_PATH,
    LWD_PROXY_SUMMARY_PATH,
    ONE_ACRE_OVERALL_SUMMARY_PATH,
    PUBLIC_ALL_MISSING_PATH,
    PUBLIC_DATA_REGISTER_PATH,
    PUBLIC_GAP_MATRIX_PATH,
    PARAMETER_ROLE_LABELS,
    current_source_label,
    has_current_state,
    render_assessment_status,
)


st.title("参数与科研依据")
render_assessment_status()
st.caption(f"当前案例包：{CASE_NAME}")
if CASE_CONFIG.get("validation_status"):
    st.caption(
        f"验证状态：{CASE_CONFIG['validation_status']}；"
        f"来源 DOI：{CASE_CONFIG.get('source_doi', '未登记')}；"
        f"许可：{CASE_CONFIG.get('source_license', '未登记')}"
    )
if not has_current_state():
    st.info("当前会话尚未提交风险情景。通用模型限制和数据缺口仍可在本页查看。")
result = st.session_state.get("current_result")
st.caption(f"当前查看：{current_source_label()}")
st.info("本页集中展示判断依据、证据来源、实际使用参数和模型限制。")

basis_tab, parameter_tab, rule_tab, gap_tab, public_data_tab = st.tabs(
    ["判断依据", "模型参数", "决策规则", "案例缺口", "公开数据扩展"]
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
        if CASE_CONFIG.get("evidence_caption"):
            st.caption(CASE_CONFIG["evidence_caption"])
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

with public_data_tab:
    st.caption(
        "项目级公开数据登记和缺口矩阵；这些数据不等于某一个案例包的本地校准结果。"
    )
    public_gaps = pd.read_csv(PUBLIC_GAP_MATRIX_PATH)
    st.dataframe(
        public_gaps[
            [
                "gap_id",
                "gap_item",
                "priority",
                "current_status",
                "what_can_be_analyzed_now",
                "what_still_requires_local_or_partner_data",
            ]
        ].rename(
            columns={
                "gap_id": "缺口编号",
                "gap_item": "缺口",
                "priority": "优先级",
                "current_status": "状态",
                "what_can_be_analyzed_now": "现在能做",
                "what_still_requires_local_or_partner_data": "仍需现场数据",
            }
        ),
        hide_index=True,
        width="stretch",
        height=420,
    )
    st.markdown("**One Acre Fund 田块描述性关联**")
    st.caption(
        "水分过量和病害均为农户二元报告。表中产量差异未经协变量调整，"
        "只能作为观察性线索，不能解释为因果效应。"
    )
    st.dataframe(
        pd.read_csv(ONE_ACRE_OVERALL_SUMMARY_PATH).rename(
            columns={
                "water_excess": "水分过量",
                "disease": "病害影响",
                "fields": "田块数",
                "mean_yield_kg_ha": "平均产量kg/ha",
                "median_yield_kg_ha": "中位产量kg/ha",
                "mean_difference_vs_no_exposure_kg_ha": "相对双无组差异kg/ha",
            }
        ),
        hide_index=True,
        width="stretch",
    )
    st.markdown("**RH≥90%代理与真实叶面湿润的比较**")
    st.caption(
        "真实湿润按叶面湿润分钟大于0或叶面传感器值大于0判定；"
        "RH为站点相对湿度。平均敏感度越低，把RH当LWD造成的漏报越严重。"
    )
    st.dataframe(
        pd.read_csv(LWD_PROXY_SUMMARY_PATH).rename(
            columns={
                "dataset": "数据集",
                "comparisons": "比较数",
                "mean_sensitivity": "平均敏感度",
                "mean_specificity": "平均特异度",
                "mean_precision": "平均精确率",
                "mean_agreement": "平均一致率",
            }
        ),
        hide_index=True,
        width="stretch",
    )
    public_register = pd.read_csv(PUBLIC_DATA_REGISTER_PATH)
    st.markdown("**公开数据登记**")
    st.dataframe(
        public_register[
            [
                "dataset_name",
                "provider",
                "doi",
                "license",
                "local_status",
                "primary_use",
                "main_limitation",
            ]
        ].rename(
            columns={
                "dataset_name": "数据集",
                "provider": "来源",
                "doi": "DOI/标识",
                "license": "许可",
                "local_status": "本地状态",
                "primary_use": "用途",
                "main_limitation": "限制",
            }
        ),
        hide_index=True,
        width="stretch",
        height=360,
    )
    st.markdown("**全部缺失字段清单**")
    all_missing = pd.read_csv(PUBLIC_ALL_MISSING_PATH)
    st.dataframe(
        all_missing[
            [
                "data_id",
                "domain",
                "data_item",
                "priority",
                "current_public_status",
                "public_substitute",
                "minimal_record_unit",
            ]
        ].rename(
            columns={
                "data_id": "编号",
                "domain": "类别",
                "data_item": "缺失数据",
                "priority": "优先级",
                "current_public_status": "公开状态",
                "public_substitute": "公开替代",
                "minimal_record_unit": "最小记录单元",
            }
        ),
        hide_index=True,
        width="stretch",
        height=480,
    )
