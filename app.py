import streamlit as st


st.set_page_config(
    page_title="洪涝次生灾害风险决策系统",
    page_icon="🌽",
    layout="wide",
)

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
    <div class="app-brand">🌽 洪涝次生灾害风险决策系统</div>
    <div style="font-size: 0.78rem; opacity: 0.65;">v0.6 公开证据原型</div>
    """,
    unsafe_allow_html=True,
)

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
        ],
        "科研依据": [
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
