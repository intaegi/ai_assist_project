import html

import requests
import streamlit as st
import streamlit.components.v1 as components

from frontend.api_client import ApiError


def _save_form(client, case_id: str) -> None:
    prefix = f"form_{case_id}_"
    payload = {
        "approval_form": {
            "title": st.session_state.get(prefix + "title", ""),
            "vendor": st.session_state.get(prefix + "vendor", ""),
            "service_name": st.session_state.get(prefix + "service_name", ""),
            "service_start_date": st.session_state.get(prefix + "service_start_date") or None,
            "service_end_date": st.session_state.get(prefix + "service_end_date") or None,
            "amount": st.session_state.get(prefix + "amount") or None,
            "approval_category_no": st.session_state.get(prefix + "approval_category_no", ""),
            "body": st.session_state.get(prefix + "body", ""),
            "required_documents": st.session_state.get(prefix + "required_documents", []),
        }
    }
    try:
        client.patch_case(case_id, payload)
        st.session_state["autosave_message"] = "自動保存しました"
    except ApiError as exc:
        st.session_state["autosave_message"] = f"自動保存に失敗しました: {exc}"


def _render_preview(client, case: dict) -> None:
    files = case.get("files", [])
    if not files:
        st.info("添付書類はありません。")
        return
    labels = [file["file_name"] for file in files]
    selected_name = st.selectbox("原本書類", labels, key=f"preview_{case['case_id']}")
    selected = files[labels.index(selected_name)]
    url = client.file_url(case["case_id"], selected["id"])
    if selected["content_type"] == "application/pdf":
        components.html(
            f'<iframe src="{html.escape(url)}" width="100%" height="620" style="border:1px solid #d1d5db;"></iframe>',
            height=640,
        )
    else:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            st.image(response.content, use_column_width=True)
        except requests.RequestException as exc:
            st.error(f"画像を表示できません: {exc}")

    st.markdown("**選択した根拠**")
    found = False
    for field, sources in case.get("field_sources", {}).items():
        for source in sources:
            if source.get("file_id") == selected["id"]:
                found = True
                st.caption(f"{field} / {source.get('page', '-')}ページ")
                st.code(source.get("quote", ""), language=None)
    if not found:
        st.caption("このファイルに紐づく抽出根拠はありません。")


def render_result_page(client, case_id: str, history_mode: bool = False) -> None:
    try:
        case = client.get_case(case_id)
    except ApiError as exc:
        st.error(str(exc))
        return
    title = case.get("title") or "決裁案"
    top_left, top_right = st.columns([4, 1])
    top_left.title(title)
    top_left.caption(f"最終更新: {case.get('updated_at', '-')}")
    if history_mode and top_right.button("新規作成へコピー", use_container_width=True):
        try:
            clone = client.clone(case_id)
            st.session_state.draft_clone = clone
            st.session_state.case_id = clone["case_id"]
            st.session_state.page = "new"
            st.success("過去履歴を新しい案件へコピーしました。日付、金額、期間を再確認してください。")
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))

    preview_col, form_col = st.columns([1.05, 1], gap="large")
    with preview_col:
        st.subheader("原本書類・根拠")
        _render_preview(client, case)

    form = case.get("approval_form", {})
    prefix = f"form_{case_id}_"
    with form_col:
        st.subheader("AI生成決裁フォーム")
        common = {"on_change": _save_form, "args": (client, case_id)}
        st.text_input("タイトル", value=form.get("title", ""), key=prefix + "title", **common)
        c1, c2 = st.columns(2)
        c1.text_input("取引先", value=form.get("vendor", ""), key=prefix + "vendor", **common)
        c2.text_input("製品・サービス名", value=form.get("service_name", ""), key=prefix + "service_name", **common)
        c1, c2 = st.columns(2)
        c1.text_input("利用開始日", value=form.get("service_start_date") or "", key=prefix + "service_start_date", **common)
        c2.text_input("利用終了日", value=form.get("service_end_date") or "", key=prefix + "service_end_date", **common)
        c1, c2 = st.columns(2)
        c1.number_input(
            "金額",
            value=float(form.get("amount") or 0),
            min_value=0.0,
            step=1000.0,
            key=prefix + "amount",
            **common,
        )
        c2.text_input(
            "決裁科目番号",
            value=form.get("approval_category_no", ""),
            key=prefix + "approval_category_no",
            **common,
        )
        st.text_area("決裁本文", value=form.get("body", ""), height=220, key=prefix + "body", **common)
        st.session_state[prefix + "required_documents"] = form.get("required_documents", [])
        if message := st.session_state.pop("autosave_message", None):
            st.caption(message)

    tabs = st.tabs(["要約", "類似決裁", "不足・注意", "チェックリスト", "修正履歴"])
    with tabs[0]:
        st.write(case.get("summary") or "要約はありません。")
    with tabs[1]:
        similar = case.get("similar_cases", [])
        if not similar:
            st.info("直接類似する過去決裁は見つかりませんでした。基準資料を優先して作成しています。")
        for item in similar:
            with st.container(border=True):
                st.markdown(f"**{item['title']}**")
                st.caption(f"類似度: {item['score']:.2f} / {item['reason']}")
    with tabs[2]:
        for item in case.get("validation_results", []):
            renderer = {
                "error": st.error,
                "warning": st.warning,
                "info": st.info,
                "success": st.success,
            }[item["severity"]]
            renderer(item["message"])
    with tabs[3]:
        for index, item in enumerate(case.get("checklist", [])):
            st.checkbox(item, key=f"check_{case_id}_{index}")
    with tabs[4]:
        for version in reversed(case.get("versions", [])):
            st.caption(f"Version {version['version']} / {version.get('created_at', '-')}")
            st.write(version.get("instruction", ""))

    st.markdown("---")
    st.subheader("AIへの修正依頼")
    instruction = st.chat_input("例: 決裁本文を承認者向けに3文以内へ短縮してください。")
    if instruction:
        try:
            with st.spinner("最新案を作成しています"):
                client.chat(case_id, instruction)
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))
