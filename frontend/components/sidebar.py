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


def _render_history_link(case: dict, active: bool) -> None:
    title = case.get("title") or case.get("description", "名称未設定")[:24]
    updated = _format_history_time(case.get("updated_at"))
    active_class = " active" if active else ""
    href = f"?case_id={quote(str(case['case_id']))}"
    time_html = f'<span class="history-time">{html.escape(updated)}</span>' if updated else ""
    st.markdown(
        f"""
        <a href="{href}" target="_self" rel="noopener noreferrer" class="history-item{active_class}">
          <span class="history-title">{html.escape(title)}</span>
          {time_html}
        </a>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(client, active_case_id: str | None) -> tuple[str, str | None]:
    page = st.session_state.get("page", "new")
    selected = active_case_id
    query_case_id = st.query_params.get("case_id")
    if query_case_id:
        page = "history"
        selected = query_case_id
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
              <span>決裁RAG</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("＋ 新規作成", use_container_width=True, type="primary" if page == "new" else "secondary"):
            st.query_params.clear()
            page = "new"
            selected = None
        if st.button(
            "⚙ 初期設定",
            use_container_width=True,
            type="primary" if page == "settings" else "secondary",
        ):
            st.query_params.clear()
            page = "settings"
        st.markdown(
            """
            <div class="sidebar-section-title">
              <span class="sidebar-section-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M3 12a9 9 0 1 0 3-6.7"/>
                  <path d="M3 4v5h5"/>
                  <path d="M12 7v5l3 2"/>
                </svg>
              </span>
              <span>作成履歴</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        try:
            cases = client.list_cases()
        except Exception:
            cases = []
        generated = [case for case in cases if case.get("current_version", 0) > 0]
        if not generated:
            st.caption("作成履歴はまだありません")
        visible_cases = generated[:4]
        hidden_cases = generated[4:]
        show_more = st.session_state.get("history_show_more", False)
        for case in visible_cases + (hidden_cases if show_more else []):
            active = page == "history" and selected == case["case_id"]
            _render_history_link(case, active)
        if hidden_cases and not show_more:
            if st.button(
                "＋ もっと見る",
                key="history_show_more_button",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state.history_show_more = True
        if active_case_id:
            st.markdown(
                f'<div class="sidebar-current-case">現在の案件<br>{html.escape(active_case_id)}</div>',
                unsafe_allow_html=True,
            )
    st.session_state.page = page
    st.session_state.case_id = selected
    return page, selected
