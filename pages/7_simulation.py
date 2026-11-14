import pandas as pd
import streamlit as st

from luohe_simulation import load_manifest as load_luohe_manifest
from luohe_simulation import load_pilot as load_luohe_pilot
from simulation_evidence import load_daily, load_manifest, load_summary
from ui_common import render_assessment_status


st.title("APSIM 虚拟实验")
render_assessment_status()

st.warning(
    "本页全部为 APSIM 模型仿真结果，不是田间实测，也不用于自动填补河南田块缺失值。"
)
st.caption(
    "数据来源：APSIM 官方玉米涝渍验证情景 MaizeLizaso；"
    "本项目在 APSIM 2026.11.8146.0 中重跑并补充水分胁迫诊断字段。"
)

summary = load_summary()
daily = load_daily()
manifest = load_manifest()

metric_columns = st.columns(4)
metric_columns[0].metric("证据等级", "模型仿真")
metric_columns[1].metric("验证情景", f"{len(summary)} 个")
metric_columns[2].metric("逐日记录", f"{len(daily):,}")
version_parts = manifest["model"].replace("APSIM ", "").split(".")
metric_columns[3].metric("APSIM", ".".join(version_parts[:2]))
st.caption(f"完整模型版本：{manifest['model']}")

st.subheader("可用仿真信息")
st.write(
    "- 可得到：积水历时、根区湿润比例、过量水胁迫、LAI、地上生物量、产量及相对变化。"
)
st.write(
    "- 不能得到：河南本地品种参数、南方锈病发生率、病害严重度或农户田块的真实产量损失。"
)
st.write(
    "- 当前验证情景使用官方模型、气象、土壤和品种配置；这些参数不能冒充河南本地参数。"
)

display = summary[
    [
        "timing",
        "drainage_hold_days",
        "water_application_mm_day",
        "ponding_days",
        "max_surface_ponding_mm",
        "max_lai",
        "max_biomass_kg_ha",
        "simulated_yield_kg_ha",
        "observed_yield_kg_ha",
        "simulated_yield_relative_to_control_pct",
        "simulation_minus_observed_pct",
    ]
].rename(
    columns={
        "timing": "处理阶段",
        "drainage_hold_days": "排水保持天数",
        "water_application_mm_day": "每日补水mm",
        "ponding_days": "模拟积水天数",
        "max_surface_ponding_mm": "最大地表积水mm",
        "max_lai": "最大LAI",
        "max_biomass_kg_ha": "最大地上生物量kg/ha",
        "simulated_yield_kg_ha": "模拟产量kg/ha",
        "observed_yield_kg_ha": "验证试验观测kg/ha",
        "simulated_yield_relative_to_control_pct": "模拟产量较对照%",
        "simulation_minus_observed_pct": "模拟值与观测偏差%",
    }
)
st.dataframe(display, hide_index=True, width="stretch")

st.subheader("产量验证")
chart_data = summary.set_index("treatment")[
    ["simulated_yield_kg_ha", "observed_yield_kg_ha"]
].rename(
    columns={
        "simulated_yield_kg_ha": "APSIM模拟",
        "observed_yield_kg_ha": "验证试验观测",
    }
)
st.bar_chart(chart_data, horizontal=True)
st.caption(
    "模拟不是观测值。4天和8天指关闭排水并每天补水的处理时长，"
    "实际模拟积水天数会因排水恢复过程而延长。"
)

labels = {
    row.treatment: (
        f"{row.timing}：{row.drainage_hold_days}天"
        if row.treatment != "control"
        else "对照：不淹水"
    )
    for row in summary.itertuples()
}
selected = st.selectbox(
    "查看逐日过程",
    options=list(labels),
    format_func=labels.get,
)
selected_summary = summary.loc[summary["treatment"] == selected].iloc[0]
selected_daily = daily.loc[daily["treatment"] == selected].copy()

cols = st.columns(4)
cols[0].metric(
    "模拟产量",
    f"{selected_summary['simulated_yield_kg_ha']:,.0f} kg/ha",
)
cols[1].metric(
    "较对照变化",
    f"{selected_summary['simulated_yield_relative_to_control_pct']:+.1f}%",
)
cols[2].metric("积水天数", f"{int(selected_summary['ponding_days'])} 天")
cols[3].metric(
    "累计过量水胁迫",
    f"{selected_summary['cumulative_excess_water_stress']:.2f}",
)

if selected != "control":
    st.caption(
        f"情景设置：{selected_summary['flood_start']} 起关闭排水并连续补水 "
        f"{int(selected_summary['drainage_hold_days'])} 天，"
        f"每日 {int(selected_summary['water_application_mm_day'])} mm；"
        f"模型地表积水持续 {int(selected_summary['ponding_days'])} 天。"
    )

surface = selected_daily.set_index("date")[["surface_ponding_mm"]].rename(
    columns={"surface_ponding_mm": "地表积水mm"}
)
stress = selected_daily.set_index("date")[
    ["wet_root_fraction", "excess_water_factor"]
].rename(
    columns={
        "wet_root_fraction": "根区湿润比例",
        "excess_water_factor": "过量水胁迫系数",
    }
)
lai = selected_daily.set_index("date")[["lai", "aboveground_kg_ha"]]

chart_1, chart_2 = st.columns(2)
with chart_1:
    st.markdown("**地表积水过程**")
    st.line_chart(surface)
with chart_2:
    st.markdown("**根区水分与胁迫**")
    st.line_chart(stress)
st.markdown("**LAI 与地上生物量**")
st.line_chart(lai)

st.subheader("河南漯河 2021 边界情景")
st.warning(
    "这组模拟使用了论文报告的真实地点、砂壤土、密度和水深下限，"
    "但品种映射为APSIM代理参数，属于定性预实验，不是ZYY432或DK517的参数校准。"
)
luohe = load_luohe_pilot()
luohe_manifest = load_luohe_manifest()
medium = luohe.loc[luohe["ks_mm_day"] == 75].copy()
proxy_labels = {"zyy432": "代理A", "dk517": "代理B"}
treatment_labels = {
    "immediate": "立即排水",
    "delayed_3d": "延迟3天",
    "no_active_drainage": "不主动排水",
}
medium["情景"] = medium.apply(
    lambda row: (
        f"{proxy_labels[row['cultivar_proxy']]}·"
        f"{treatment_labels[row['treatment']]}"
    ),
    axis=1,
)
medium["品种代理"] = medium["cultivar_proxy"].map(proxy_labels)
medium["处理"] = medium["treatment"].map(treatment_labels)
comparison = medium.set_index("情景")[
    ["simulated_yield_kg_ha", "observed_yield_kg_ha"]
].rename(
    columns={
        "simulated_yield_kg_ha": "APSIM代理模拟",
        "observed_yield_kg_ha": "论文观测",
    }
)
st.bar_chart(comparison, horizontal=True)
st.dataframe(
    medium[
        [
            "品种代理",
            "处理",
            "simulated_yield_kg_ha",
            "observed_yield_kg_ha",
            "simulated_immediate_vs_delayed_pct",
            "observed_immediate_vs_delayed_pct",
        ]
    ].rename(
        columns={
            "simulated_yield_kg_ha": "模拟产量kg/ha",
            "observed_yield_kg_ha": "论文观测kg/ha",
            "simulated_immediate_vs_delayed_pct": "模拟立即排水优势%",
            "observed_immediate_vs_delayed_pct": "观测立即排水优势%",
        }
    ),
    hide_index=True,
    width="stretch",
)
st.caption(
    "方向检验通过：两种代理均显示立即排水高于延迟3天。"
    "但模拟优势为10.2%—15.9%，低于观测的21.1%—21.8%；"
    "不主动排水情景也未复现绝产，因此暂不进入本地风险算法。"
)
with st.expander("漯河预实验的输入与限制", expanded=False):
    st.write(
        f"- 站点：{luohe_manifest['site']['latitude']}°N，"
        f"{luohe_manifest['site']['longitude']}°E，"
        f"海拔{luohe_manifest['site']['elevation_m']} m。"
    )
    st.write(
        f"- 降雨：{luohe_manifest['event']['start']} 至 "
        f"{luohe_manifest['event']['end']}，累计"
        f"{luohe_manifest['event']['rain_mm']:.2f} mm。"
    )
    st.write(f"- 水深边界：{luohe_manifest['forcing_interpretation']}")
    st.write(f"- 土壤：{luohe_manifest['soil']}")
    st.write(f"- 作物：{luohe_manifest['crop']['proxy_warning']}")

with st.expander("数据来源与使用边界", expanded=False):
    st.write(f"- 验证模型：{manifest['validation_model_url']}")
    st.write(f"- 输入气象：{manifest['weather_url']}")
    st.write(f"- 验证观测：{manifest['observation_url']}")
    st.write(f"- 产量换算：{manifest['yield_unit_source']}")
    st.write(
        "- 不允许用于：" + "、".join(manifest["not_for"]) + "。"
    )
    st.download_button(
        "下载仿真汇总CSV",
        data=pd.read_csv(
            "data/simulation/lizaso_maize_1991_summary.csv"
        ).to_csv(index=False).encode("utf-8-sig"),
        file_name="lizaso_maize_1991_summary.csv",
        mime="text/csv",
    )
