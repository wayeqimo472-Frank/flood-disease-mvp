import streamlit as st

from case_pack import DEFAULT_CASE_ID, available_case_ids, get_case_pack
from storage import initialize_database
from ui_common import activate_case
from ui_theme import apply_app_theme


st.set_page_config(
    page_title="农田涝渍与作物病害风险决策支持系统",
    page_icon=":material/agriculture:",
    layout="wide",
)

apply_app_theme()
initialize_database()
st.sidebar.markdown(
    """
    <div class="app-brand">
        <div class="app-brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
                <path d="M5 23.5C10.5 20 14.2 15.8 16 10.5C17.8 15.8 21.5 20 27 23.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>
                <path d="M9.5 23.5C12.2 21.8 14.4 19.2 16 15.8C17.6 19.2 19.8 21.8 22.5 23.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>
            </svg>
        </div>
        <div>
            <div class="app-brand-title">农田风险决策台</div>
            <div class="app-brand-meta">涝渍 · 作物 · 病害</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

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
st.sidebar.caption("多区域案例版 v0.8.3")
activate_case(selected_case_id)
case_pack = get_case_pack(selected_case_id)

navigation = st.navigation(
    {
        "决策台": [
            st.Page(
                "pages/1_overview.py",
                title="项目总览",
                icon=":material/home:",
                url_path="overview",
                default=True,
            ),
        ],
        "风险研判": [
            st.Page(
                "pages/2_risk.py",
                title="风险情景筛查",
                icon=":material/monitoring:",
                url_path="risk",
            ),
            st.Page(
                "pages/3_intervention.py",
                title="干预窗口分析",
                icon=":material/schedule:",
                url_path="intervention",
            ),
        ],
        "田野数据": [
            st.Page(
                "pages/4_field_data.py",
                title="田块数据管理",
                icon=":material/dataset:",
                url_path="field-data",
            ),
            st.Page(
                "pages/6_integration.py",
                title="数据拼接与公开案例",
                icon=":material/hub:",
                url_path="integration",
            ),
        ],
        "科研与证据": [
            st.Page(
                "pages/7_simulation.py",
                title="APSIM 虚拟实验",
                icon=":material/science:",
                url_path="simulation",
            ),
            st.Page(
                "pages/5_evidence.py",
                title="参数与科研依据",
                icon=":material/menu_book:",
                url_path="evidence",
            ),
        ],
    }
)
navigation.run()
