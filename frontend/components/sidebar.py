import html
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import streamlit as st


def _format_history_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%m/%d %H:%M")
    except ValueError:
        return value


def render_sidebar(client, active_case_id: str | None) -> tuple[str, str | None]:
    page = st.session_state.get("page", "new")
    selected = active_case_id
    query_case_id = st.query_params.get("case_id")
    if query_case_id:
        page = "history"
        selected = query_case_id
    with st.sidebar:
        st.markdown("## 決裁RAG")
        if st.button("新規作成", use_container_width=True, type="primary" if page == "new" else "secondary"):
            st.query_params.clear()
            page = "new"
            selected = None
        if st.button(
            "初期設定",
            use_container_width=True,
            type="primary" if page == "settings" else "secondary",
        ):
            st.query_params.clear()
            page = "settings"
        st.markdown("---")
        st.markdown("**作成履歴**")
        try:
            cases = client.list_cases()
        except Exception:
            cases = []
        generated = [case for case in cases if case.get("current_version", 0) > 0]
        if not generated:
            st.caption("作成履歴はまだありません")
        for case in generated[:20]:
            label = case.get("title") or case.get("description", "名称未設定")[:24]
            is_active_history = page == "history" and selected == case["case_id"]
            active_class = " active" if is_active_history else ""
            st.markdown(
                (
                    f'<a class="history-item{active_class}" '
                    f'href="?case_id={quote(case["case_id"])}" target="_self">'
                    f'<span class="history-title">{html.escape(label)}</span>'
                    f'<span class="history-time">{html.escape(_format_history_time(case.get("updated_at")))}</span>'
                    "</a>"
                ),
                unsafe_allow_html=True,
            )
        if active_case_id:
            st.markdown("---")
            st.caption(f"現在の案件\n{active_case_id}")
    st.session_state.page = page
    st.session_state.case_id = selected
    return page, selected
