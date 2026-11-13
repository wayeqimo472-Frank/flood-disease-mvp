import pandas as pd
import streamlit as st

from public_evidence_db import load_public_evidence
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
st.info("本页集中展示公开案例、判断依据、证据来源、实际使用参数和模型限制。")

basis_tab, parameter_tab, rule_tab, gap_tab, public_data_tab = st.tabs(
    ["判断依据", "模型参数", "决策规则", "案例缺口", "公开数据扩展"]
)

with public_tab:
    catalog = load_public_evidence("dataset_catalog")
    flood_case = load_public_evidence("flood_ndvi_case")
    case_metrics = load_public_evidence("flood_case_metrics")
    survival = load_public_evidence("waterlogging_survival")
    disease_progress = load_public_evidence("disease_progress")

    st.info(
        "公开案例用于展示可追溯的外源证据。不同试验的作物、地点、变量和尺度"
        "并不一致，因此本系统不把它们拟合成一个“洪涝导致病害”的因果系数。"
    )
    st.caption(
        "存储层：随应用发布的只读SQLite证据库。"
        "当前不持久保存用户上传、田块观测或农户敏感数据。"
    )
    metric_cols = st.columns(4)
    imported_count = catalog["integration_status"].str.startswith("已导入").sum()
    metric_cols[0].metric("已导入数据集", f"{imported_count} 组")
    metric_cols[1].metric("自然洪涝案例", "1 个")
    metric_cols[2].metric("涝渍基因型", f"{len(survival)} 个")
    metric_cols[3].metric("病害进展记录", f"{len(disease_progress)} 条")

    st.subheader("真实洪涝案例：灾前与灾后恢复轨迹")
    case_values = case_metrics.set_index("metric")["value"].to_dict()
    st.caption(
        "2021年自然淹水持续约24小时，退水后土壤饱和至少7天；"
        "同一遗传材料的2020年未淹田作为生育期对齐对照。"
    )
    case_cols = st.columns(3)
    case_cols[0].metric("田面明水", f"{case_values['田面明水持续时间']:g} 小时")
    case_cols[1].metric(
        "退水后土壤饱和",
        f"≥{case_values['退水后土壤饱和持续时间']:g} 天",
    )
    case_cols[2].metric(
        "存活株数降幅",
        f"{case_values['洪水后存活株数降幅']:.2f}%",
    )

    time_index = (
        flood_case["relative_timepoint"]
        .str.extract(r"(前|后)(\d+)天")
        .apply(
            lambda row: (
                -int(row[1]) if row[0] == "前" else int(row[1])
            ),
            axis=1,
        )
    )
    flood_chart = (
        flood_case.assign(relative_day=time_index)
        .pivot_table(
            index="relative_day",
            columns="condition",
            values="mean_ndvi",
            aggfunc="first",
        )
        .sort_index()
    )
    flood_chart.index.name = "相对洪水的天数"
    st.line_chart(flood_chart)
    st.caption(
        "数据来源：10.5281/zenodo.14261169（CC0）。NDVI为可用田块记录均值；"
        "对照年份的时点按原研究GDU窗口对齐，不是该对照田真实经历过洪水的日期。"
    )
    with st.expander("查看NDVI时序数据"):
        st.dataframe(
            flood_case.rename(
                columns={
                    "condition": "场景",
                    "season": "年份",
                    "date": "日期",
                    "relative_timepoint": "相对时点",
                    "mean_ndvi": "平均NDVI",
                    "plot_count": "可用田块记录数",
                    "source_id": "来源",
                    "source_note": "说明",
                }
            ),
            hide_index=True,
            width="stretch",
        )

    st.subheader("玉米9天涝渍存活率")
    survival_bins = pd.cut(
        survival["survival_pct"],
        bins=[-0.1, 25, 50, 75, 100],
        labels=["0—25%", "25—50%", "50—75%", "75—100%"],
    )
    survival_distribution = (
        survival_bins.value_counts(sort=False)
        .rename_axis("存活率区间")
        .to_frame("基因型数量")
    )
    st.bar_chart(survival_distribution)
    st.caption(
        f"80个基因型的中位存活率为{survival['survival_pct'].median():g}%，"
        f"范围为{survival['survival_pct'].min():g}%—"
        f"{survival['survival_pct'].max():g}%。"
        "来源：10.5281/zenodo.23651962（CC BY 4.0）。"
    )
    with st.expander("查看80个基因型记录"):
        st.dataframe(
            survival.rename(
                columns={
                    "genotype": "基因型",
                    "survival_pct": "9天涝渍存活率（%）",
                    "thousand_grain_weight_g": "千粒重（g）",
                    "condition": "处理",
                    "source_id": "来源",
                    "evidence_scope": "证据边界",
                }
            ),
            hide_index=True,
            width="stretch",
            height=320,
        )

    st.subheader("玉米病害时间进展参数")
    st.caption(
        "参数来自巴西两季田间试验。B1、B2、B3为单分子模型的原始拟合参数，"
        "只用于解释病害随时间的进展，不进入本系统的风险分数。"
    )
    st.dataframe(
        disease_progress[
            [
                "record_id",
                "season",
                "hybrid",
                "disease",
                "max_severity_pct",
                "initial_inoculum_parameter",
                "epidemic_rate_parameter",
                "r_squared",
                "evidence_scope",
            ]
        ].rename(
            columns={
                "record_id": "记录",
                "season": "季别",
                "hybrid": "杂交种",
                "disease": "病害",
                "max_severity_pct": "最大严重度（%）",
                "initial_inoculum_parameter": "B2初始菌量参数",
                "epidemic_rate_parameter": "B3流行速率参数",
                "r_squared": "R²",
                "evidence_scope": "适用边界",
            }
        ),
        hide_index=True,
        width="stretch",
    )

    with st.expander("公开数据集来源、许可证与接入状态"):
        st.dataframe(
            catalog.rename(
                columns={
                    "dataset_id": "数据集编号",
                    "title": "数据集",
                    "crop": "作物",
                    "dataset_type": "数据类型",
                    "repository": "仓库",
                    "doi": "DOI",
                    "license": "许可证",
                    "coverage": "覆盖范围",
                    "app_use": "页面用途",
                    "integration_status": "接入状态",
                    "evidence_level": "证据类型",
                    "limitations": "限制",
                }
            ),
            hide_index=True,
            width="stretch",
            height=360,
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
