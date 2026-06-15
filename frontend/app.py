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
      .block-container { padding-top: 3.75rem; padding-bottom: 3rem; max-width: 1500px; }
      [data-testid="stSidebar"] { border-right: 1px solid #d9dee7; }
      [data-stale="true"] { opacity: 1 !important; }
      .history-item {
        display: block;
        color: inherit !important;
        text-decoration: none !important;
        padding: 0.65rem 0.75rem;
        margin: 0.2rem 0;
        border-left: 3px solid transparent;
        background: transparent;
      }
      .history-item:hover { background: #e8f1f8; }
      .history-item.active { background: #dcecf8; border-left-color: #1769aa; }
      .history-title {
        display: block;
        line-height: 1.35;
        overflow-wrap: anywhere;
      }
      .history-time {
        display: block;
        margin-top: 0.3rem;
        color: #667085;
        font-size: 0.75rem;
        text-align: right;
      }
      h1 { font-size: 1.75rem !important; letter-spacing: 0; }
      h2, h3 { letter-spacing: 0; }
      div[data-testid="stForm"] { border: 0; padding: 0; }
      div[data-testid="stStatusWidget"] { margin-top: 0.75rem; }
      div[data-testid="stChatMessage"] { padding: 0.75rem 1rem; }
      div[data-testid="stFormSubmitButton"] button { min-height: 2.75rem; }
      button[kind="primary"] { background: #1769aa; border-color: #1769aa; }
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
