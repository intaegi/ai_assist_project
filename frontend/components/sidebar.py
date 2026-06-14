import streamlit as st


def render_sidebar(client, active_case_id: str | None) -> tuple[str, str | None]:
    page = st.session_state.get("page", "new")
    selected = active_case_id
    with st.sidebar:
        st.markdown("## 決裁RAG")
        if st.button("新規作成", use_container_width=True, type="primary" if page == "new" else "secondary"):
            page = "new"
            selected = None
        if st.button("初期設定", use_container_width=True):
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
            if st.button(label, key=f"history_{case['case_id']}", use_container_width=True):
                page = "history"
                selected = case["case_id"]
        if active_case_id:
            st.markdown("---")
            st.caption(f"現在の案件\n{active_case_id}")
    st.session_state.page = page
    st.session_state.case_id = selected
    return page, selected
