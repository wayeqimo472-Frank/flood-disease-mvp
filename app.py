import streamlit as st

from case_pack import DEFAULT_CASE_ID, available_case_ids, get_case_pack
from storage import initialize_database
from ui_common import activate_case


st.set_page_config(
    page_title="农田涝渍与作物病害风险决策支持系统",
    page_icon="🌽",
    layout="wide",
)

initialize_database()
st.sidebar.markdown(
    """
    <style>
    [data-testid="stSidebarContent"] {
        display: flex;
        flex-direction: column;
    }
    [data-testid="stSidebarUserContent"] {
        order: -1;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid rgba(49, 51, 63, 0.12);
    }
    .app-brand {
        font-size: 1.15rem;
        font-weight: 700;
        line-height: 1.35;
        margin-bottom: 0.25rem;
    }
    </style>
    <div class="app-brand">🌽 农田涝渍与作物病害风险决策支持系统</div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.caption("多区域案例版 v0.8.1")

case_ids = available_case_ids()
default_index = case_ids.index(DEFAULT_CASE_ID) if DEFAULT_CASE_ID in case_ids else 0
if len(case_ids) > 1:
    selected_case_id = st.sidebar.selectbox(
        "当前案例",
        options=case_ids,
        index=default_index,
        format_func=lambda value: get_case_pack(value).name,
        key="selected_case_id",
    )
else:
    selected_case_id = case_ids[0] if case_ids else DEFAULT_CASE_ID
activate_case(selected_case_id)
case_pack = get_case_pack(selected_case_id)

navigation = st.navigation(
    {
        "工作空间": [
            st.Page(
                "pages/1_overview.py",
                title="项目总览",
                icon="🏠",
                url_path="overview",
                default=True,
            ),
            st.Page(
                "pages/2_risk.py",
                title="风险情景筛查",
                icon="🌽",
                url_path="risk",
            ),
            st.Page(
                "pages/3_intervention.py",
                title="干预窗口分析",
                icon="⏱",
                url_path="intervention",
            ),
        ],
        "数据管理": [
            st.Page(
                "pages/4_field_data.py",
                title="田块数据管理",
                icon="📁",
                url_path="field-data",
            ),
            st.Page(
                "pages/6_integration.py",
                title="数据拼接与公开案例",
                icon="🛰",
                url_path="integration",
            ),
        ],
        "科研依据": [
            st.Page(
                "pages/7_simulation.py",
                title="APSIM 虚拟实验",
                icon="🧪",
                url_path="simulation",
            ),
            st.Page(
                "pages/5_evidence.py",
                title="参数与科研依据",
                icon="📚",
                url_path="evidence",
            ),
        ],
    }
)
navigation.run()
