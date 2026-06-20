import sys
from pathlib import Path

import streamlit as st

# `streamlit run frontend/app.py` also needs the repository root on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.api_client import ApiClient, ApiError
from frontend.components.new_case_page import render_new_case_page
from frontend.components.result_page import render_result_page
from frontend.components.settings_page import render_settings_page
from frontend.components.sidebar import render_sidebar


st.set_page_config(
    page_title="決裁RAGアシスタント",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root {
        --app-accent: #7C3AED;
        --app-accent-dark: #6D28D9;
        --app-accent-soft: #F3EEFF;
        --app-bg: #FFFFFF;
        --app-sidebar: #FFFFFF;
        --app-border: #E6E6E6;
        --app-soft: #F7F7F8;
        --app-text: #111111;
        --app-muted: #667085;
      }
      .stApp { background: var(--app-bg); }
      .block-container {
        padding-top: 2.25rem;
        padding-bottom: 3.5rem;
        max-width: 1440px;
      }
      [data-testid="stSidebar"] {
        background: var(--app-sidebar);
        border-right: 1px solid var(--app-border);
      }
      [data-testid="stSidebar"] > div,
      [data-testid="stSidebar"] [data-testid="stSidebarContent"],
      [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        background: var(--app-sidebar) !important;
      }
      [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.5rem;
      }
      [data-stale="true"] { opacity: 1 !important; }
      .sidebar-brand {
        display: flex;
        align-items: center;
        margin: 0.2rem 0 1.15rem;
        padding-left: 0.65rem;
        border-left: 4px solid var(--app-accent);
        color: var(--app-text);
        font-size: 1.1rem;
        font-weight: 700;
      }
      .brand-mark {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.8rem;
        height: 1.8rem;
        border-radius: 0.55rem;
        color: #fff;
        background: var(--app-accent);
        font-size: 0.95rem;
        font-weight: 800;
      }
      .sidebar-section-title {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        margin: 1.55rem 0 0.45rem;
        color: var(--app-text);
        font-size: 0.92rem;
        font-weight: 800;
        letter-spacing: 0.01em;
      }
      .sidebar-section-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.1rem;
        height: 1.1rem;
        color: var(--app-accent-dark);
      }
      .sidebar-section-icon svg {
        width: 1.05rem;
        height: 1.05rem;
        fill: none;
        stroke: currentColor;
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
      }
      [data-testid="stSidebar"] div[data-testid="stButton"] button {
        min-height: 2.65rem;
        justify-content: flex-start;
        padding: 0.45rem 0.9rem;
        border-radius: 0.75rem;
        border: 1px solid transparent;
        box-shadow: none;
        font-weight: 600;
      }
      [data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
        color: #fff;
        background: var(--app-accent);
        border-color: var(--app-accent);
      }
      [data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"] {
        color: var(--app-text);
        background: transparent;
      }
      [data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"]:hover {
        background: #F1F5F9;
        border-color: transparent;
      }
      .history-item {
        display: grid;
        grid-template-columns: 1.25rem 1fr;
        gap: 0.5rem;
        color: inherit !important;
        text-decoration: none !important;
        padding: 0.52rem 0.65rem;
        margin: 0.1rem 0;
        border: 1px solid transparent;
        border-radius: 0.8rem;
        background: transparent;
      }
      .history-item:hover { background: #F8FAFC; }
      .history-item.active {
        background: var(--app-accent-soft);
        border-color: #DDD6FE;
        color: #4C1D95 !important;
      }
      .history-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.25rem;
        height: 1.25rem;
        margin-top: 0.08rem;
        border-radius: 0.38rem;
        color: #4C1D95;
        background: var(--app-accent-soft);
        font-size: 0.72rem;
        font-weight: 800;
      }
      .history-title {
        display: block;
        line-height: 1.28;
        font-size: 0.92rem;
        overflow-wrap: anywhere;
      }
      .history-time {
        display: block;
        margin-top: 0.2rem;
        color: var(--app-muted);
        font-size: 0.68rem;
        text-align: right;
      }
      .history-more {
        margin-top: 0.2rem;
      }
      .history-more summary {
        display: block;
        padding: 0.52rem 0.65rem;
        color: var(--app-text);
        border-radius: 0.75rem;
        cursor: pointer;
        font-size: 0.9rem;
        font-weight: 600;
      }
      .history-more summary:hover {
        background: #F8FAFC;
      }
      .history-more summary::-webkit-details-marker {
        display: none;
      }
      .sidebar-current-case {
        margin-top: 1.25rem;
        padding: 0.75rem;
        border: 1px solid var(--app-border);
        border-radius: 0.8rem;
        color: var(--app-muted);
        background: #fff;
        font-size: 0.78rem;
        overflow-wrap: anywhere;
      }
      h1 { font-size: 1.75rem !important; letter-spacing: 0; }
      h2, h3 { letter-spacing: 0; }
      h1, h2, h3, h4 { color: var(--app-text); }
      div[data-testid="stForm"] { border: 0; padding: 0; }
      div[data-testid="stStatusWidget"] { margin-top: 0.75rem; }
      div[data-testid="stChatMessage"] { padding: 0.75rem 1rem; }
      div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
        border-color: var(--app-border);
        background: #ffffff;
        box-shadow: none;
      }
      div[data-testid="stAlert"] { border-radius: 10px; }
      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input,
      textarea,
      div[data-baseweb="select"] > div {
        border-radius: 8px;
        background-color: var(--app-soft);
        border-color: var(--app-border);
      }
      div[data-testid="stTextInput"] input:focus,
      div[data-testid="stNumberInput"] input:focus,
      textarea:focus {
        border-color: var(--app-accent) !important;
        box-shadow: 0 0 0 1px var(--app-accent) !important;
      }
      div[data-testid="stFormSubmitButton"] button { min-height: 2.75rem; }
      button {
        border-radius: 0.75rem !important;
        box-shadow: none !important;
      }
      button[kind="primary"] {
        background: var(--app-accent);
        border-color: var(--app-accent);
        color: #fff;
      }
      button[kind="primary"]:hover {
        background: var(--app-accent-dark);
        border-color: var(--app-accent-dark);
      }
      .section-kicker {
        color: var(--app-muted);
        font-size: 0.86rem;
        margin-top: -0.25rem;
        margin-bottom: 0.75rem;
      }
      .app-page-kicker {
        display: inline-flex;
        align-items: center;
        margin-bottom: 0.15rem;
        padding-left: 0.55rem;
        border-left: 4px solid var(--app-accent);
        color: #4C1D95;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.04em;
      }
      .app-page-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.45rem;
        height: 1.45rem;
        border-radius: 0.45rem;
        color: #fff;
        background: var(--app-accent);
        font-size: 0.9rem;
      }
      .app-section-heading {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        margin: 1rem 0 0.55rem;
        color: var(--app-text);
        font-size: 1.05rem;
        font-weight: 800;
      }
      .app-section-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 1.45rem;
        height: 1.25rem;
        padding: 0 0.35rem;
        border-radius: 999px;
        color: #fff;
        background: var(--app-accent);
        font-size: 0.72rem;
        font-weight: 800;
      }
      .result-header {
        margin-bottom: 0.75rem;
      }
      .result-title {
        margin: 0.2rem 0 0.15rem;
        color: var(--app-text);
        font-size: 1.65rem;
        line-height: 1.25;
        font-weight: 800;
      }
      .result-updated {
        color: var(--app-muted);
        font-size: 0.85rem;
      }
      .result-summary-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 0.3rem 0 1rem;
      }
      .result-summary-card {
        padding: 0.85rem 1rem;
        border: 1px solid var(--app-border);
        border-radius: 0.85rem;
        background: #fff;
      }
      .result-summary-label {
        color: var(--app-muted);
        font-size: 0.78rem;
        font-weight: 700;
      }
      .result-summary-value {
        margin-top: 0.25rem;
        color: var(--app-text);
        font-size: 1.05rem;
        font-weight: 800;
      }
      @media (max-width: 900px) {
        .result-summary-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

client = ApiClient()
if not st.session_state.get("backend_health_checked"):
    try:
        backend_health = client.health()
        st.session_state.backend_health_checked = True
        st.session_state.backend_features = backend_health.get("features", [])
    except ApiError as exc:
        st.error(str(exc))
        st.code("uvicorn backend.app.main:app --reload --port 8000")
        st.stop()

if "checklist_verification" not in st.session_state.get("backend_features", []):
    st.warning(
        "FastAPIが旧バージョンで起動しています。"
        "チェックリストAI確認を利用するにはバックエンドを再起動してください。"
    )

page, case_id = render_sidebar(client, st.session_state.get("case_id"))

if page == "settings":
    render_settings_page(client)
elif page in {"result", "history"} and case_id:
    render_result_page(client, case_id, history_mode=page == "history")
else:
    render_new_case_page(client)
