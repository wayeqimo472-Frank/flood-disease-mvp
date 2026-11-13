import json
from pathlib import Path

import pandas as pd
import streamlit as st

from data_integration import (
    ICASA_MAPPING_PATH,
    geometry_template,
    load_icasa_mapping,
    parse_geojson_geometries,
    parse_sar_metrics_csv,
    sar_metrics_template,
    seed_reference_data,
)
from public_evidence_db import load_public_evidence
from storage import (
    DEFAULT_DB_PATH,
    list_external_datasets,
    list_plot_flood_metrics,
    list_plot_geometries,
    load_external_records,
    save_plot_flood_metrics,
    save_plot_geometries,
)
from ui_common import CASE_CONFIG, CASE_NAME, render_assessment_status


PROJECT_DIR = Path(__file__).resolve().parents[1]
US_VALIDATION_PATH = (
    PROJECT_DIR
    / "case_packs"
    / "us_corn_belt_cscap_2011_2015"
    / "processed"
    / "validation_summary.json"
)
PUBLIC_REGISTER_PATH = PROJECT_DIR / "data" / "public_dataset_register_v0.2.csv"


st.title("数据拼接与公开案例")
render_assessment_status()
st.caption(f"当前案例包：{CASE_NAME}")
st.info(
    "本页把 ICASA 字段标准、FTW 田块边界、SAR 洪水指标和公开观测案例"
    "接到同一套数据管理中。遥感推算与现场实测分开保存，不互相替代。"
)

datasets = list_external_datasets()
if not datasets:
    st.warning("当前数据库还没有导入公开数据索引。")
    if st.button("导入仓库内公开数据", type="primary"):
        with st.spinner("正在导入美国 CSCAP 和公开证据数据..."):
            imported = seed_reference_data()
        st.success(f"已处理 {len(imported)} 个公开数据文件。")
        st.rerun()

overview_tab, us_tab, public_tab, geospatial_tab = st.tabs(
    ["数据总览", "美国玉米带", "公开案例", "地理与标准接口"]
)

with overview_tab:
    datasets = list_external_datasets()
    if datasets:
        inventory = pd.DataFrame(datasets)
        total_rows = int(inventory["row_count"].sum())
        us_rows = int(
            inventory.loc[inventory["category"] == "US CSCAP", "row_count"].sum()
        )
        geometries = list_plot_geometries(limit=10000)
        flood_metrics = list_plot_flood_metrics(limit=10000)
        metric_cols = st.columns(4)
        metric_cols[0].metric("已导入文件", len(inventory))
        metric_cols[1].metric("外部记录", f"{total_rows:,}")
        metric_cols[2].metric("美国 CSCAP 记录", f"{us_rows:,}")
        metric_cols[3].metric("地块几何 / SAR 指标", f"{len(geometries)} / {len(flood_metrics)}")
        st.caption(
            f"统一写入本地 SQLite：{DEFAULT_DB_PATH}。"
            "CSV 文件哈希用于避免重复导入；来源文件变化时才会替换对应记录。"
        )
        st.dataframe(
            inventory[
                [
                    "title",
                    "category",
                    "evidence_level",
                    "license",
                    "row_count",
                    "imported_at",
                    "source_path",
                ]
            ].rename(
                columns={
                    "title": "数据集",
                    "category": "类别",
                    "evidence_level": "证据等级",
                    "license": "许可",
                    "row_count": "记录数",
                    "imported_at": "导入时间",
                    "source_path": "本地来源",
                }
            ),
            hide_index=True,
            width="stretch",
            height=420,
        )
        st.markdown(
            "**证据等级：** `observed` 为现场或试验观测，"
            "`remote_sensed` 为遥感结果，`derived` 为派生统计，"
            "`metadata` 为目录或缺口信息。"
        )
    else:
        st.write("导入完成后，这里会显示所有公开数据和记录数。")

with us_tab:
    if not US_VALIDATION_PATH.is_file():
        st.error("缺少美国 CSCAP 校验摘要。")
    else:
        validation = json.loads(US_VALIDATION_PATH.read_text(encoding="utf-8"))
        metric_cols = st.columns(4)
        metric_cols[0].metric("试验点", validation["sites"])
        metric_cols[1].metric("产量记录", f"{validation['corn_yield_rows']:,}")
        metric_cols[2].metric("病害评级", f"{validation['disease_rating_rows']:,}")
        metric_cols[3].metric("匹配产量观测", validation["disease_observation_rows"])
        st.caption(
            "来源 DOI：10.15482/USDA.ADC/1411953，许可 CC0。"
            "美国数据只用于外部观测和监测框架，不作本地定量风险校准。"
        )

        yield_frame = load_external_records("us_cscap_corn_yield")
        disease_frame = load_external_records("us_cscap_disease_ratings")
        operation_frame = load_external_records("us_cscap_field_operations")

        chart_col_1, chart_col_2 = st.columns(2)
        with chart_col_1:
            st.subheader("年度平均产量")
            if not yield_frame.empty:
                yield_chart = (
                    yield_frame.groupby("year", as_index=True)["yield_kg_ha"]
                    .mean()
                    .rename("平均产量 kg/ha")
                )
                st.line_chart(yield_chart)
                st.caption("按站点和小区的原始产量直接求年度均值，未作协变量调整。")
        with chart_col_2:
            st.subheader("病害评级构成")
            if not disease_frame.empty:
                disease_chart = (
                    disease_frame["disease_code"]
                    .value_counts()
                    .rename_axis("病害")
                    .to_frame("评级记录数")
                )
                st.bar_chart(disease_chart)
                st.caption("数值评级主要集中在穗腐和茎腐，不代表全部玉米病害。")

        st.subheader("数据内容")
        data_choice = st.selectbox(
            "查看美国案例数据表",
            options=[
                "站点元数据",
                "玉米产量",
                "病害评级",
                "病害产量匹配",
                "田间作业",
                "地下水位",
                "排水流量",
            ],
        )
        dataset_lookup = {
            "站点元数据": "us_cscap_site_metadata",
            "玉米产量": "us_cscap_corn_yield",
            "病害评级": "us_cscap_disease_ratings",
            "病害产量匹配": "us_cscap_disease_yield_matched",
            "田间作业": "us_cscap_field_operations",
            "地下水位": "us_cscap_water_table_daily",
            "排水流量": "us_cscap_tile_flow_daily",
        }
        selected_frame = load_external_records(dataset_lookup[data_choice], limit=500)
        if selected_frame.empty:
            st.info("该数据表尚未导入。请先在“数据总览”执行导入。")
        else:
            st.caption(f"最多显示前 500 行；当前表共 {len(selected_frame)} 行。")
            st.dataframe(selected_frame, hide_index=True, width="stretch", height=360)
        st.warning(
            "美国公开数据没有同一田块的明水开始、实际退水、洪前病情、"
            "涝后连续病情和最终产量完整序列。不能把不同站点或不同小区拼成因果关系。"
        )

with public_tab:
    st.caption(
        "公开案例来自不同国家、作物、年份和试验尺度。"
        "这里展示原始证据和项目派生摘要，不拟合跨试验的洪涝—病害因果系数。"
    )
    try:
        catalog = load_public_evidence("dataset_catalog")
        flood_case = load_public_evidence("flood_ndvi_case")
        case_metrics = load_public_evidence("flood_case_metrics")
        survival = load_public_evidence("waterlogging_survival")
        disease_progress = load_public_evidence("disease_progress")
    except FileNotFoundError:
        st.error("缺少公开证据只读数据库。")
    else:
        case_values = case_metrics.set_index("metric")["value"].to_dict()
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

        relative_days = (
            flood_case["relative_timepoint"]
            .str.extract(r"(前|后)(\d+)天")
            .apply(
                lambda row: -int(row[1]) if row[0] == "前" else int(row[1]),
                axis=1,
            )
        )
        flood_chart = (
            flood_case.assign(relative_day=relative_days)
            .pivot_table(
                index="relative_day",
                columns="condition",
                values="mean_ndvi",
                aggfunc="first",
            )
            .sort_index()
        )
        flood_chart.index.name = "相对洪水的天数"
        st.subheader("真实淹水田与未淹对照的 NDVI 轨迹")
        st.line_chart(flood_chart)
        st.caption(
            "来源：10.5281/zenodo.14261169，CC0。NDVI 是可用田块记录均值；"
            "2020 年对照时点按原研究 GDU 窗口对齐。"
        )

        chart_col_1, chart_col_2 = st.columns(2)
        with chart_col_1:
            st.subheader("9 天涝渍存活率分布")
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
                f"80 个基因型的中位存活率为 {survival['survival_pct'].median():g}%。"
                "来源：10.5281/zenodo.23651962，CC BY 4.0。"
            )
        with chart_col_2:
            st.subheader("病害时间进展拟合参数")
            st.dataframe(
                disease_progress[
                    [
                        "season",
                        "hybrid",
                        "disease",
                        "max_severity_pct",
                        "epidemic_rate_parameter",
                        "r_squared",
                    ]
                ].rename(
                    columns={
                        "season": "季别",
                        "hybrid": "杂交种",
                        "disease": "病害",
                        "max_severity_pct": "最大严重度（%）",
                        "epidemic_rate_parameter": "流行速率参数",
                        "r_squared": "R²",
                    }
                ),
                hide_index=True,
                width="stretch",
                height=420,
            )
        with st.expander("公开案例来源、许可证和限制"):
            st.dataframe(
                catalog[
                    [
                        "title",
                        "crop",
                        "repository",
                        "doi",
                        "license",
                        "integration_status",
                        "limitations",
                    ]
                ].rename(
                    columns={
                        "title": "数据集",
                        "crop": "作物",
                        "repository": "来源",
                        "doi": "DOI",
                        "license": "许可",
                        "integration_status": "接入状态",
                        "limitations": "限制",
                    }
                ),
                hide_index=True,
                width="stretch",
                height=360,
            )

        if PUBLIC_REGISTER_PATH.is_file():
            st.subheader("公开数据登记")
            register = pd.read_csv(PUBLIC_REGISTER_PATH)
            st.dataframe(
                register[
                    [
                        "dataset_name",
                        "provider",
                        "license",
                        "local_status",
                        "primary_use",
                        "main_limitation",
                    ]
                ].rename(
                    columns={
                        "dataset_name": "数据集",
                        "provider": "来源",
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

with geospatial_tab:
    st.subheader("ICASA 标准字段映射")
    mapping = load_icasa_mapping()
    mapping_cols = st.columns(4)
    mapping_cols[0].metric("映射字段", len(mapping))
    mapping_cols[1].metric("精确对应", int((mapping["mapping_strength"] == "exact").sum()))
    mapping_cols[2].metric("需转换", int((mapping["mapping_strength"] == "derived").sum()))
    mapping_cols[3].metric("无通用标准", int((mapping["mapping_strength"] == "no_standard").sum()))
    st.caption(
        "采用 ICASA Data Dictionary 的字段子集，不安装 DSSAT。"
        "代码和字典为 BSD-3-Clause；无通用标准的关键字段继续由本项目扩展字段保存。"
    )
    st.dataframe(
        mapping[
            [
                "local_field",
                "local_meaning",
                "icasa_variable_name",
                "icasa_code_display",
                "icasa_unit",
                "mapping_strength",
                "mapping_note",
            ]
        ].rename(
            columns={
                "local_field": "本地字段",
                "local_meaning": "含义",
                "icasa_variable_name": "ICASA 字段",
                "icasa_code_display": "代码",
                "icasa_unit": "单位",
                "mapping_strength": "映射强度",
                "mapping_note": "说明",
            }
        ),
        hide_index=True,
        width="stretch",
        height=360,
    )
    st.download_button(
        "下载 ICASA 字段映射",
        data=ICASA_MAPPING_PATH.read_bytes(),
        file_name=ICASA_MAPPING_PATH.name,
        mime="text/csv",
    )

    st.divider()
    st.subheader("田块几何：FTW 预测或现场绘制")
    geometry_source = st.selectbox(
        "几何来源",
        options=["ftw_prediction", "field_survey"],
        format_func=lambda value: {
            "ftw_prediction": "FTW 模型预测边界",
            "field_survey": "现场测绘或人工勾画边界",
        }[value],
    )
    st.caption(
        "FTW 代码许可为 MIT，模型检查点可能使用独立许可。"
        "页面只接收 GeoJSON FeatureCollection，并要求每个要素含 properties.field_id。"
    )
    geometry_upload = st.file_uploader(
        "上传田块 GeoJSON",
        type=["geojson", "json"],
        key="plot_geometry_upload",
    )
    st.download_button(
        "下载 GeoJSON 接口模板",
        data=geometry_template(),
        file_name="plot_geometry_template_v0.1.geojson",
        mime="application/geo+json",
    )
    if geometry_upload is not None:
        try:
            geometries = parse_geojson_geometries(
                geometry_upload.getvalue(),
                case_id=CASE_CONFIG["case_id"],
                source=geometry_source,
            )
            inserted = save_plot_geometries(geometries)
        except ValueError as error:
            st.error(str(error))
        else:
            st.success(
                f"GeoJSON 校验通过，共 {len(geometries)} 个田块；"
                f"本次新增 {inserted} 条，重复记录已跳过。"
            )

    st.divider()
    st.subheader("地块洪水指标：SAR 或遥感 worker 输出")
    st.caption(
        "优先研究 Sentinel-1 SAR。该表记录地块淹没比例、洪水起止和退水日，"
        "统一标记为 remote_sensed；实际水深和实际退水时间仍以现场记录为准。"
    )
    sar_source = st.text_input(
        "指标来源",
        value="sentinel1_sar_worker",
        help="例如 sentinel1_sar_worker 或合作方遥感处理服务。",
    )
    sar_upload = st.file_uploader(
        "上传地块洪水指标 CSV",
        type=["csv"],
        key="sar_metrics_upload",
    )
    st.download_button(
        "下载 SAR 指标 CSV 模板",
        data=sar_metrics_template(),
        file_name="plot_flood_metrics_template_v0.1.csv",
        mime="text/csv",
    )
    if sar_upload is not None:
        try:
            metrics = parse_sar_metrics_csv(
                sar_upload.getvalue(),
                case_id=CASE_CONFIG["case_id"],
                source=sar_source.strip() or "sentinel1_sar_worker",
            )
            inserted = save_plot_flood_metrics(metrics)
        except ValueError as error:
            st.error(str(error))
        else:
            st.success(
                f"CSV 校验通过，共 {len(metrics)} 条地块指标；"
                f"本次新增 {inserted} 条，重复记录已跳过。"
            )

    stored_geometries = list_plot_geometries()
    stored_metrics = list_plot_flood_metrics()
    if not stored_geometries.empty:
        st.subheader("已保存的田块几何")
        st.dataframe(
            stored_geometries[
                [
                    "field_id",
                    "case_id",
                    "source",
                    "evidence_level",
                    "quality",
                    "geometry_type",
                    "created_at",
                ]
            ],
            hide_index=True,
            width="stretch",
        )
    if not stored_metrics.empty:
        st.subheader("已保存的洪水指标")
        st.dataframe(stored_metrics, hide_index=True, width="stretch")

    st.markdown(
        "- [Fields of the World / FTW](https://github.com/fieldsoftheworld/ftw-baselines)："
        "代码 MIT，用于可选田块边界推理。\n"
        "- [Sen1Floods11](https://github.com/cloudtostreet/Sen1Floods11)："
        "SAR 洪水研究参考；许可证和模型条款核实前不打包进运行时。\n"
        "- [farmOS](https://github.com/farmOS/farmOS)：只借鉴田块、观测、作业和资产模型；"
        "核心为 GPL，未复制代码。"
    )
