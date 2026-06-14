import streamlit as st

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
      .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1500px; }
      [data-testid="stSidebar"] { border-right: 1px solid #d9dee7; }
      h1 { font-size: 1.75rem !important; letter-spacing: 0; }
      h2, h3 { letter-spacing: 0; }
      div[data-testid="stForm"] { border: 0; padding: 0; }
      button[kind="primary"] { background: #1769aa; border-color: #1769aa; }
    </style>
    """,
    unsafe_allow_html=True,
)

client = ApiClient()
try:
    client.health()
except ApiError as exc:
    st.error(str(exc))
    st.code("uvicorn backend.app.main:app --reload --port 8000")
    st.stop()

page, case_id = render_sidebar(client, st.session_state.get("case_id"))

if page == "settings":
    render_settings_page(client)
elif page in {"result", "history"} and case_id:
    render_result_page(client, case_id, history_mode=page == "history")
else:
    render_new_case_page(client)
