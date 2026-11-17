from pathlib import Path

import streamlit as st


THEME_CSS_PATH = Path(__file__).resolve().parent / "assets" / "app.css"


def apply_app_theme() -> None:
    """Apply the shared product visual language to every Streamlit route."""
    css = THEME_CSS_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
