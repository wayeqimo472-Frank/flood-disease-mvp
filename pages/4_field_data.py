import sqlite3
from datetime import datetime
from hashlib import sha256

import pandas as pd
import streamlit as st

from batch_io import assess_csv, result_csv, template_csv
from storage import (
    DEFAULT_DB_PATH,
    create_backup,
    initialize_database,
    list_import_batches,
    load_batch_results,
    load_raw_batch,
    save_import_batch,
)
from ui_common import CASE_CONFIG, CASE_PACK, DISEASE_LABELS, render_assessment_status


initialize_database()
st.title("田块数据管理")
render_assessment_status()
st.caption(
    "每行代表一个田块在某次观测时点的记录。空单元格保留为未知，不按0处理；"
    "同一田块可提交多行表示重复观测。"
)
st.info(
    f"CSV计算完成后写入本地SQLite数据库：{DEFAULT_DB_PATH}。"
    "刷新页面或重启应用后，导入批次仍可重新载入。"
)
st.caption(
    "当前仍是单用户、无登录模式；页面切换保留当前上传，数据库保存每次不同内容的导入批次。"
    "相同文件按SHA256自动去重，不重复入库。"
)
if st.button("创建本地数据库备份"):
    try:
        backup_path = create_backup()
    except (OSError, sqlite3.Error, ValueError) as error:
        st.error(f"备份失败：{error}")
    else:
        st.success(f"备份已创建：{backup_path}")


def _clear_field_upload() -> None:
    st.session_state.pop("field_upload", None)
    st.session_state.pop("field_uploader", None)

template_col, upload_col = st.columns([0.7, 1.3], gap="large")
with template_col:
    st.download_button(
        "下载空白CSV模板",
        data=template_csv(),
        file_name="field_observation_template_v0.6.csv",
        mime="text/csv",
        width="stretch",
    )
    with st.expander("CSV字段与取值说明", expanded=False):
        disease_codes = "、".join(f"`{key}`" for key in DISEASE_LABELS)
        st.markdown(
            f"""
            - `case_id`：当前默认 `{CASE_PACK.case_id}`；留空时使用当前案例包
            - 地区与作物：`region_code`、`country_code`、`crop_code`
            - 行政层级：`admin_level_1`、`admin_level_2`，可保留原 `county`、`village`
            - 当前案例疾病输入代码：{disease_codes}
            - 症状：`none`、`sparse`、`obvious`
            - 诊断：`not_assessed`、`suspected`、`confirmed_fungal`、`confirmed_nonfungal`
            - 基线：`unknown`、`none`、`sporadic`、`established`
            - 水状态：`yes`、`no`、`unknown`
            - 病害压力：`low`、`moderate`、`high`、`unknown`
            - 统一产量单位：`yield_kg_ha`；统一成本单位：`intervention_cost_per_ha`
            - 货币：`currency_code`，当前案例默认 `{CASE_CONFIG.get("currency_code", "")}`
            - `field_id`为必填；数值缺失可留空
            """
        )
with upload_col:
    uploaded_csv = st.file_uploader(
        "上传田块记录CSV",
        type=["csv"],
        accept_multiple_files=False,
        key="field_uploader",
    )

if uploaded_csv is not None:
    content = uploaded_csv.getvalue()
    signature = sha256(content).hexdigest()
    current_upload = st.session_state.get("field_upload")
    if current_upload is None or current_upload["signature"] != signature:
        try:
            batch_results, batch_errors = assess_csv(content)
        except ValueError as error:
            st.error(f"新上传文件未应用：{error}")
        else:
            version = 1 if current_upload is None else current_upload["version"] + 1
            try:
                batch_id = save_import_batch(
                    uploaded_csv.name,
                    content,
                    batch_results,
                    batch_errors,
                )
            except (OSError, sqlite3.Error, ValueError) as error:
                batch_id = None
                st.error(f"文件已计算，但写入数据库失败：{error}")
            st.session_state.field_upload = {
                "file_name": uploaded_csv.name,
                "content": content,
                "size": len(content),
                "uploaded_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
                "signature": signature,
                "version": version,
                "results": batch_results,
                "errors": batch_errors,
                "batch_id": batch_id,
            }

current_upload = st.session_state.get("field_upload")
if current_upload is None:
    st.caption("当前会话暂无上传记录。")
else:
    st.subheader("当前会话上传")
    st.write(
        f"**文件：** {current_upload['file_name']}  "
        f"**版本：** v{current_upload['version']}  "
        f"**大小：** {current_upload['size'] / 1024:.1f} KB  "
        f"**上传时间：** {current_upload['uploaded_at']}  "
        f"**数据库批次：** "
        f"{current_upload['batch_id'] if current_upload.get('batch_id') else '未写入'}"
    )
    st.button("清除当前会话上传", on_click=_clear_field_upload)
    batch_errors = current_upload["errors"]
    batch_results = current_upload["results"]
    if not batch_errors.empty:
        st.error(
            f"有 {len(batch_errors)} 行校验失败；其余 {len(batch_results)} 行已正常计算。"
        )
        st.dataframe(batch_errors, hide_index=True, width="stretch")
    if not batch_results.empty:
        st.success(f"当前版本包含 {len(batch_results)} 条有效记录。")
        st.dataframe(batch_results, hide_index=True, width="stretch", height=320)
        stdownload, original_download = st.columns(2)
        with stdownload:
            st.download_button(
                "下载原始字段＋计算结果CSV",
                data=result_csv(batch_results),
                file_name="field_assessment_results_v0.4.csv",
                mime="text/csv",
                width="stretch",
            )
        with original_download:
            st.download_button(
                "下载原始上传CSV",
                data=current_upload["content"],
                file_name=current_upload["file_name"],
                mime="text/csv",
                width="stretch",
            )
    elif batch_errors.empty:
        st.warning("CSV没有数据行。")

history = list_import_batches(limit=12)
if history:
    st.subheader("本地数据库导入历史")
    history_frame = pd.DataFrame(history)[
        [
            "batch_id",
            "file_name",
            "case_ids",
            "valid_rows",
            "invalid_rows",
            "size_bytes",
            "imported_at",
        ]
    ].rename(
        columns={
            "batch_id": "批次",
            "file_name": "文件",
            "case_ids": "案例包",
            "valid_rows": "有效行",
            "invalid_rows": "错误行",
            "size_bytes": "字节",
            "imported_at": "导入时间",
        }
    )
    st.dataframe(history_frame, hide_index=True, width="stretch")
    batch_ids = [item["batch_id"] for item in history]
    selected_batch_id = st.selectbox(
        "载入数据库批次",
        options=batch_ids,
        format_func=lambda value: f"批次 {value}",
        key="history_batch_id",
    )
    persisted_results = load_batch_results(selected_batch_id)
    if not persisted_results.empty:
        st.caption(f"批次 {selected_batch_id} 共 {len(persisted_results)} 条有效记录。")
        st.dataframe(
            persisted_results,
            hide_index=True,
            width="stretch",
            height=280,
        )
        persisted_name, persisted_raw = load_raw_batch(selected_batch_id)
        result_download, raw_download = st.columns(2)
        with result_download:
            st.download_button(
                "下载数据库批次计算结果",
                data=result_csv(persisted_results),
                file_name=f"batch_{selected_batch_id}_results.csv",
                mime="text/csv",
                width="stretch",
            )
        with raw_download:
            st.download_button(
                "下载数据库原始CSV",
                data=persisted_raw,
                file_name=persisted_name,
                mime="text/csv",
                width="stretch",
            )
