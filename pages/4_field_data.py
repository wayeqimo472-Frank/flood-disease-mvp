from datetime import datetime
from hashlib import sha256

import streamlit as st

from batch_io import assess_csv, result_csv, template_csv
from ui_common import render_assessment_status


st.title("田块数据管理")
render_assessment_status()
st.caption(
    "每行代表一个田块在某次观测时点的记录。空单元格保留为未知，不按0处理；"
    "同一田块可提交多行表示重复观测。"
)
st.info("当前为单次会话内的CSV处理，不建立数据库，也不在服务器持久保存上传文件。")
st.caption(
    "页面切换会保留当前上传；刷新页面、关闭浏览器或开启新会话后不保证保留。"
    "上传不同文件会替换当前会话中的上一版本。"
)


def _clear_field_upload() -> None:
    st.session_state.pop("field_upload", None)
    st.session_state.pop("field_uploader", None)

template_col, upload_col = st.columns([0.7, 1.3], gap="large")
with template_col:
    st.download_button(
        "下载空白CSV模板",
        data=template_csv(),
        file_name="field_observation_template_v0.4.csv",
        mime="text/csv",
        width="stretch",
    )
    with st.expander("CSV字段与取值说明", expanded=False):
        st.markdown(
            """
            - 疾病输入代码：`southern_rust`、`stem_rot`、`leaf_spot`、`ear_rot`
            - 症状：`none`、`sparse`、`obvious`
            - 诊断：`not_assessed`、`suspected`、`confirmed_fungal`、`confirmed_nonfungal`
            - 基线：`unknown`、`none`、`sporadic`、`established`
            - 水状态：`yes`、`no`、`unknown`
            - 病害压力：`low`、`moderate`、`high`、`unknown`
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
            st.session_state.field_upload = {
                "file_name": uploaded_csv.name,
                "content": content,
                "size": len(content),
                "uploaded_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
                "signature": signature,
                "version": version,
                "results": batch_results,
                "errors": batch_errors,
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
        f"**上传时间：** {current_upload['uploaded_at']}"
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
