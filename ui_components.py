from __future__ import annotations

from html import escape

import streamlit as st


def _chips(items: list[str] | tuple[str, ...]) -> str:
    return "".join(
        f'<span class="page-chip">{escape(str(item))}</span>' for item in items
    )


def page_header(
    title: str,
    subtitle: str | None = None,
    meta: list[str] | tuple[str, ...] | None = None,
) -> None:
    with st.container(key="page-heading"):
        st.title(title)
        if subtitle:
            st.caption(subtitle)
        if meta:
            st.html(
                f'<div class="page-meta">{_chips(meta)}</div>',
            )


def section_header(title: str, description: str | None = None) -> None:
    st.subheader(title)
    if description:
        st.caption(description)


def module_label(label: str) -> str:
    return f'<span class="module-label">{escape(label)}</span>'


def render_overview_hero(
    *,
    has_result: bool,
    source_label: str,
    risk_label: str,
    flood_value: str,
    waterlog_value: str,
) -> None:
    if has_result:
        title = "先处理眼前暴露，再决定病害路径"
        body = (
            f"{source_label}已经提交。当前处置优先级为“{risk_label}”，"
            "下一步应完成排水、巡田和必要的诊断记录。"
        )
        action_label = "查看干预窗口"
        action_url = "/intervention"
        status = "已提交计算"
    else:
        title = "从一块田开始，建立可追溯的风险判断"
        body = (
            "录入明水、渍水、作物状态与病害证据，系统会明确区分情景假设、"
            "已提交输入和仍然未知的内容。"
        )
        action_label = "开始风险筛查"
        action_url = "/risk"
        status = "等待首次输入"

    st.html(
        f"""
        <section class="overview-hero">
            <img
                class="overview-hero-image"
                src="app/static/images/corn-field.jpg"
                alt="农田作物行景观，仅作界面氛围"
            >
            <div class="overview-hero-scrim"></div>
            <div class="overview-hero-copy">
                <div class="hero-status"><i></i>{escape(status)}</div>
                <h2>{escape(title)}</h2>
                <p>{escape(body)}</p>
                <div class="hero-facts">
                    <div><span>明水</span><strong>{escape(flood_value)}</strong></div>
                    <div><span>渍水</span><strong>{escape(waterlog_value)}</strong></div>
                    <div><span>处置优先级</span><strong>{escape(risk_label)}</strong></div>
                </div>
                <a class="hero-action" href="{action_url}" target="_self">
                    {escape(action_label)} <span aria-hidden="true">→</span>
                </a>
            </div>
            <div class="overview-hero-note">场景图片仅作界面氛围，不代表项目田块实测。</div>
        </section>
        """
    )


def render_quick_routes() -> None:
    st.html(
        """
        <div class="route-board">
            <a class="route-card route-card-primary" href="/risk" target="_self">
                <span class="route-number">01</span>
                <span class="route-copy">
                    <strong>风险情景筛查</strong>
                    <span>录入涝渍暴露、病害证据和环境条件。</span>
                </span>
                <span class="route-arrow" aria-hidden="true">→</span>
            </a>
            <a class="route-card" href="/intervention" target="_self">
                <span class="route-number">02</span>
                <span class="route-copy">
                    <strong>干预窗口</strong>
                    <span>查看排水、巡查、诊断和防治的约束。</span>
                </span>
                <span class="route-arrow" aria-hidden="true">→</span>
            </a>
            <a class="route-card" href="/field-data" target="_self">
                <span class="route-number">03</span>
                <span class="route-copy">
                    <strong>田块数据</strong>
                    <span>导入、校验并批量计算田间记录。</span>
                </span>
                <span class="route-arrow" aria-hidden="true">→</span>
            </a>
            <a class="route-card" href="/integration" target="_self">
                <span class="route-number">04</span>
                <span class="route-copy">
                    <strong>公开案例与拼接</strong>
                    <span>查看公开数据、几何接口和案例证据。</span>
                </span>
                <span class="route-arrow" aria-hidden="true">→</span>
            </a>
        </div>
        """
    )


def render_boundary_module(items: list[str]) -> None:
    rows = "".join(
        f'<li><span>{index:02d}</span><p>{escape(item)}</p></li>'
        for index, item in enumerate(items, start=1)
    )
    st.html(
        f"""
        <section class="boundary-module">
            <div class="boundary-media">
                <img
                    src="app/static/images/field-aerial.jpg"
                    alt="农田近景，仅作界面氛围"
                >
                <div>
                    <small>场景图片仅作界面氛围</small>
                    <strong>判断必须保留边界</strong>
                </div>
            </div>
            <ol class="boundary-list">{rows}</ol>
        </section>
        """
    )


def render_window_cards(windows: list[dict[str, str]]) -> None:
    cards = []
    for index, item in enumerate(windows, start=1):
        status = escape(item["status"])
        cards.append(
            f"""
            <article class="window-card">
                <div class="window-index">{index:02d}</div>
                <div class="window-head">
                    <h3>{escape(item["window"])}</h3>
                    <span>{status}</span>
                </div>
                <p class="window-action">{escape(item["action"])}</p>
                <p class="window-evidence">{escape(item["evidence"])}</p>
            </article>
            """
        )
    st.html(
        f'<div class="window-grid">{"".join(cards)}</div>',
    )


def render_supporting_media() -> None:
    st.html(
        """
        <section class="supporting-media">
            <img
                src="app/static/images/farmland.jpg"
                alt="田间作业场景，仅作界面氛围"
            >
            <div>
                <h3>从证据到动作</h3>
                <p>系统保留输入、规则、证据等级和缺失项，但不以单一分数替代田间判断。</p>
            </div>
        </section>
        """
    )
