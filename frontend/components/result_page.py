import json
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import pypdfium2 as pdfium
import requests
import streamlit as st
import streamlit.components.v1 as components

from frontend.api_client import ApiError
from frontend.document_comparison import build_comparison_rows


FORM_STATE_FIELDS = (
    "title",
    "vendor",
    "service_name",
    "service_start_date",
    "service_end_date",
    "amount",
    "approval_category_no",
    "body",
    "required_documents",
)

def _render_revision_logs(logs: list[dict]) -> None:
    for log in logs:
        role = log.get("role", "assistant")
        with st.chat_message(role if role in {"user", "assistant"} else "assistant"):
            st.write(log.get("message", ""))


def _clear_form_state(case_id: str) -> None:
    prefix = f"form_{case_id}_"
    for field in FORM_STATE_FIELDS:
        st.session_state.pop(prefix + field, None)


def _format_datetime(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def _form_copy_text(form: dict) -> str:
    amount = form.get("amount")
    amount_text = f"{float(amount):,.0f}円" if amount not in (None, "") else ""
    return "\n".join(
        [
            f"タイトル: {form.get('title', '')}",
            f"取引先: {form.get('vendor', '')}",
            f"製品・サービス名: {form.get('service_name', '')}",
            f"利用期間: {form.get('service_start_date') or ''} ～ {form.get('service_end_date') or ''}",
            f"金額: {amount_text}",
            f"決裁科目番号: {form.get('approval_category_no', '')}",
            "",
            "決裁本文:",
            str(form.get("body", "")),
        ]
    )


def _current_form_from_state(case_id: str, form: dict) -> dict:
    prefix = f"form_{case_id}_"
    return {
        "title": st.session_state.get(prefix + "title", form.get("title", "")),
        "vendor": st.session_state.get(prefix + "vendor", form.get("vendor", "")),
        "service_name": st.session_state.get(prefix + "service_name", form.get("service_name", "")),
        "service_start_date": st.session_state.get(
            prefix + "service_start_date",
            form.get("service_start_date"),
        ),
        "service_end_date": st.session_state.get(prefix + "service_end_date", form.get("service_end_date")),
        "amount": st.session_state.get(prefix + "amount", form.get("amount")),
        "approval_category_no": st.session_state.get(
            prefix + "approval_category_no",
            form.get("approval_category_no", ""),
        ),
        "body": st.session_state.get(prefix + "body", form.get("body", "")),
        "required_documents": form.get("required_documents", []),
    }


def _render_copy_button(form: dict) -> None:
    text = json.dumps(_form_copy_text(form), ensure_ascii=False).replace("</", "<\\/")
    components.html(
        f"""
        <button id="copy-form" type="button" aria-label="フォーム内容をコピー">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M8 7V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-2"/>
            <rect x="4" y="7" width="12" height="14" rx="2"/>
          </svg>
          <span>フォームコピー</span>
        </button>
        <script>
          const button = document.getElementById("copy-form");
          button.addEventListener("click", async () => {{
            const text = {text};
            try {{
              await navigator.clipboard.writeText(text);
            }} catch (error) {{
              const area = document.createElement("textarea");
              area.value = text;
              document.body.appendChild(area);
              area.select();
              document.execCommand("copy");
              area.remove();
            }}
            button.classList.add("copied");
            window.clearTimeout(window.copyTimer);
            window.copyTimer = window.setTimeout(() => button.classList.remove("copied"), 700);
          }});
        </script>
        <style>
          body {{
            margin: 0;
            height: 40px;
            display: flex;
            justify-content: flex-end;
            align-items: center;
            overflow: hidden;
            font-family: sans-serif;
          }}
          button {{
            width: 100%;
            height: 38px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            border: 1px solid #c4b5fd;
            border-radius: 8px;
            color: #6d28d9;
            background: #fff;
            cursor: pointer;
            font-size: 12px;
            font-weight: 700;
          }}
          svg {{
            width: 17px;
            height: 17px;
            fill: none;
            stroke: currentColor;
            stroke-width: 1.8;
            stroke-linecap: round;
            stroke-linejoin: round;
            vertical-align: middle;
          }}
          button:hover {{ background: #f3eeff; border-color: #7c3aed; }}
          button:focus {{ outline: 2px solid #c4b5fd; outline-offset: 1px; }}
          button.copied {{ background: #f3eeff; border-color: #7c3aed; }}
        </style>
        """,
        height=40,
    )


def _render_field_copy_button(
    label: str,
    value: object,
    compact: bool = False,
) -> None:
    text = "" if value is None else str(value)
    serialized = json.dumps(text, ensure_ascii=False).replace("</", "<\\/")
    components.html(
        f"""
        <button
          id="copy-field"
          type="button"
          aria-label="{html.escape(label)}をコピー"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M8 7V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-2"/>
            <rect x="4" y="7" width="12" height="14" rx="2"/>
          </svg>
        </button>
        <script>
          const button = document.getElementById("copy-field");
          button.addEventListener("click", async () => {{
            const text = {serialized};
            try {{
              await navigator.clipboard.writeText(text);
            }} catch (error) {{
              const area = document.createElement("textarea");
              area.value = text;
              document.body.appendChild(area);
              area.select();
              document.execCommand("copy");
              area.remove();
            }}
            button.classList.add("copied");
            window.clearTimeout(window.copyTimer);
            window.copyTimer = window.setTimeout(() => button.classList.remove("copied"), 700);
          }});
        </script>
        <style>
          body {{
            margin: 0;
            padding-top: 29px;
            overflow: hidden;
            font-family: sans-serif;
            white-space: nowrap;
          }}
          button {{
            width: 100%;
            min-height: 38px;
            padding: 0 2px;
            border: 1px solid #c4b5fd;
            border-radius: 8px;
            color: #6d28d9;
            background: #fff;
            cursor: pointer;
            font-size: 11px;
          }}
          svg {{
            width: 17px;
            height: 17px;
            fill: none;
            stroke: currentColor;
            stroke-width: 1.8;
            stroke-linecap: round;
            stroke-linejoin: round;
            vertical-align: middle;
          }}
          button:hover {{ background: #f3eeff; border-color: #7c3aed; }}
          button:focus {{ outline: 2px solid #c4b5fd; outline-offset: 1px; }}
          button.copied {{ background: #f3eeff; border-color: #7c3aed; }}
        </style>
        """,
        height=76,
    )


def _text_input_with_copy(
    input_col,
    copy_col,
    label: str,
    value: str,
    key: str,
    common: dict,
    compact: bool = False,
) -> None:
    input_col.text_input(label, value=value, key=key, **common)
    with copy_col:
        _render_field_copy_button(
            label,
            st.session_state.get(key, value),
            compact=compact,
        )


def _number_input_with_copy(
    input_col,
    copy_col,
    label: str,
    value: float,
    key: str,
    common: dict,
    compact: bool = False,
) -> None:
    input_col.number_input(
        label,
        value=value,
        min_value=0.0,
        step=1000.0,
        key=key,
        **common,
    )
    with copy_col:
        current = st.session_state.get(key, value)
        copy_value = f"{float(current):g}" if current is not None else ""
        _render_field_copy_button(label, copy_value, compact=compact)


def _copyable_text_input(
    label: str,
    value: str,
    key: str,
    common: dict,
) -> None:
    input_col, copy_col = st.columns([9, 1], gap="small")
    _text_input_with_copy(input_col, copy_col, label, value, key, common)


def _copyable_number_input(
    label: str,
    value: float,
    key: str,
    common: dict,
) -> None:
    input_col, copy_col = st.columns([9, 1], gap="small")
    _number_input_with_copy(input_col, copy_col, label, value, key, common)


def _copyable_text_area(
    label: str,
    value: str,
    key: str,
    common: dict,
) -> None:
    input_col, copy_col = st.columns([9, 1], gap="small")
    input_col.text_area(label, value=value, height=120, key=key, **common)
    with copy_col:
        _render_field_copy_button(label, st.session_state.get(key, value))


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
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        if selected["content_type"] == "application/pdf":
            pdf = pdfium.PdfDocument(response.content)
            for page_index in range(min(len(pdf), 5)):
                page = pdf[page_index]
                bitmap = page.render(scale=1.5)
                image = bitmap.to_pil().copy()
                st.caption(f"{page_index + 1}ページ")
                st.image(image, use_column_width=True)
                bitmap.close()
                page.close()
            pdf.close()
            st.markdown(
                f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">'
                "原本PDFを別タブで開く</a>",
                unsafe_allow_html=True,
            )
        else:
            st.image(response.content, use_column_width=True)
    except (requests.RequestException, pdfium.PdfiumError) as exc:
        st.error(f"原本を表示できません: {exc}")


def _render_document_recovery(client, case: dict) -> None:
    actionable = [
        item
        for item in case.get("validation_results", [])
        if "upload_file" in item.get("actions", [])
    ]
    if not actionable:
        return

    missing_names = []
    for item in actionable:
        document = (item.get("basis") or {}).get("document")
        if document and document not in missing_names:
            missing_names.append(document)

    input_version_key = f"recovery_input_version_{case['case_id']}"
    input_version = st.session_state.get(input_version_key, 0)

    with st.container(border=True):
        st.markdown("##### 不足書類を追加して再確認")
        if missing_names:
            st.caption("現在不足している書類: " + "、".join(missing_names))
        with st.form(f"recovery_form_{case['case_id']}", clear_on_submit=False):
            files = st.file_uploader(
                "追加書類",
                type=["pdf", "jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key=f"recovery_files_{case['case_id']}_{input_version}",
            )
            instruction = st.text_area(
                "AIへの反映指示",
                value="追加した書類の内容を確認し、決裁フォーム、要約、チェックリストを更新してください。",
                height=90,
                key=f"recovery_instruction_{case['case_id']}_{input_version}",
            )
            regenerate = st.checkbox(
                "追加書類を反映してAI決裁案を再作成する",
                value=True,
                key=f"recovery_regenerate_{case['case_id']}_{input_version}",
            )
            submitted = st.form_submit_button(
                "📎 書類を追加して再確認",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not files:
                st.warning("追加書類を1件以上選択してください。")
                return
            try:
                added_names = []
                skipped_names = []
                with st.status("追加書類を確認しています", expanded=True) as status:
                    for file in files or []:
                        response = client.add_file(case["case_id"], file)
                        upload_result = response.get("file_upload", {})
                        if upload_result.get("added", True):
                            added_names.append(file.name)
                            st.write(f"{file.name} を保存しました")
                        else:
                            skipped_names.append(file.name)
                            st.write(f"{file.name} は登録済みのためスキップしました")
                    if regenerate:
                        st.write("追加書類を反映してAI決裁案を再作成しています")
                        client.generate(
                            case["case_id"],
                            instruction.strip()
                            or "追加書類を反映して決裁案を再作成",
                        )
                    _clear_form_state(case["case_id"])
                    status.update(
                        label="追加書類の再確認が完了しました",
                        state="complete",
                        expanded=False,
                    )
                messages = []
                if added_names:
                    messages.append(f"追加保存: {len(added_names)}件")
                if skipped_names:
                    messages.append(
                        "重複のためスキップ: " + "、".join(skipped_names)
                    )
                messages.append("不足・注意とチェックリストを再確認しました。")
                st.session_state["document_recovery_message"] = " / ".join(messages)
                st.session_state[input_version_key] = input_version + 1
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))


def _render_checklist(client, case: dict) -> None:
    checklist = case.get("checklist", [])
    if not checklist:
        st.caption("確認項目はありません。")
        return

    if st.button(
        "✅ チェックリストをAIで確認",
        type="primary",
        use_container_width=True,
        key=f"verify_checklist_{case['case_id']}",
    ):
        try:
            with st.spinner("添付書類とフォームを照合しています"):
                client.verify_checklist(case["case_id"])
            st.rerun()
        except ApiError as exc:
            if exc.status_code == 404:
                st.error(
                    "チェックリスト確認APIが見つかりません。"
                    "FastAPIを最新コードで再起動してください。"
                )
            else:
                st.error(str(exc))

    verification = {
        item["item"]: item
        for item in case.get("checklist_verification", [])
    }
    for index, item in enumerate(checklist):
        st.checkbox(item, key=f"check_{case['case_id']}_{index}")
        result = verification.get(item)
        if not result:
            continue
        evidence = " / ".join(result.get("evidence", []))
        status_label = {
            "verified": "AI確認: 確認済み",
            "action_required": "AI確認: 要対応",
            "not_verifiable": "AI確認: 確認不可",
        }[result["status"]]
        message = f"{status_label} - {result.get('message', '')}"
        if evidence:
            message = f"{message} 根拠: {evidence}"
        renderer = {
            "verified": st.success,
            "action_required": st.warning,
            "not_verifiable": st.info,
        }[result["status"]]
        renderer(message)


def _render_confirmation_summary(case: dict, current_form: dict) -> None:
    validation_results = case.get("validation_results", [])
    blocking_count = sum(
        1
        for item in validation_results
        if item.get("severity") in {"error", "warning"}
    )
    checklist = case.get("checklist", [])
    verification = case.get("checklist_verification", [])
    verified_count = sum(1 for item in verification if item.get("status") == "verified")
    documents = current_form.get("required_documents", [])
    required_documents_text = "、".join(documents) if documents else "-"
    checklist_text = (
        f"{verified_count}/{len(checklist)} 確認済み"
        if verification
        else f"{len(checklist)}件 / AI確認前"
    )
    issue_text = "注意なし" if blocking_count == 0 else f"{blocking_count}件の確認事項"
    st.markdown(
        f"""
        <div class="result-summary-grid">
          <div class="result-summary-card">
            <div class="result-summary-label">不足・注意</div>
            <div class="result-summary-value">{html.escape(issue_text)}</div>
          </div>
          <div class="result-summary-card">
            <div class="result-summary-label">チェックリスト</div>
            <div class="result-summary-value">{html.escape(checklist_text)}</div>
          </div>
          <div class="result-summary-card">
            <div class="result-summary-label">必要書類</div>
            <div class="result-summary-value">{html.escape(required_documents_text)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result_page(client, case_id: str, history_mode: bool = False) -> None:
    try:
        case = client.get_case(case_id)
    except ApiError as exc:
        st.error(str(exc))
        return
    title = case.get("title") or "決裁案"
    header_col, action_col = st.columns([3.2, 1], gap="large")
    with header_col:
        st.markdown(
            (
                '<div class="result-header">'
                f'<h1 class="result-title">{html.escape(title)}</h1>'
                f'<div class="result-updated">最終更新: {html.escape(_format_datetime(case.get("updated_at")))}</div>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )
    copy_clicked = False
    if history_mode:
        with action_col:
            st.write("")
            copy_clicked = st.button(
                "＋ 新規作成へコピー",
                type="primary",
                use_container_width=True,
            )
    if copy_clicked:
        try:
            clone = client.clone(case_id)
            st.session_state.draft_clone = clone
            st.session_state.case_id = clone["case_id"]
            st.session_state.page = "new"
            st.success("過去履歴を新しい案件へコピーしました。日付、金額、期間を再確認してください。")
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))

    st.markdown(
        '<div class="app-section-heading">生成結果表示</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="result-pair-marker"></div>', unsafe_allow_html=True)
    preview_col, form_col = st.columns([4, 6], gap="small")
    with preview_col:
        with st.container(border=True):
            st.subheader("📄 原本書類")
            st.caption("AIが参照した原本を確認できます。")
            _render_preview(client, case)

    form = case.get("approval_form", {})
    prefix = f"form_{case_id}_"
    current_form = _current_form_from_state(case_id, form)
    with form_col:
        with st.container(border=True):
            form_title_col, form_copy_col = st.columns([3.2, 1.15], gap="small")
            with form_title_col:
                st.subheader("📝 AI生成決裁フォーム")
            with form_copy_col:
                _render_copy_button(current_form)
            st.markdown(
                '<div class="section-kicker">AIが抽出した値です。右側のアイコンで個別コピーできます。</div>',
                unsafe_allow_html=True,
            )
            common = {"on_change": _save_form, "args": (client, case_id)}
            _copyable_text_input(
                "タイトル",
                form.get("title", ""),
                prefix + "title",
                common,
            )
            _copyable_text_input(
                "取引先",
                form.get("vendor", ""),
                prefix + "vendor",
                common,
            )
            _copyable_text_input(
                "製品・サービス名",
                form.get("service_name", ""),
                prefix + "service_name",
                common,
            )
            _copyable_text_input(
                "利用開始日",
                form.get("service_start_date") or "",
                prefix + "service_start_date",
                common,
            )
            _copyable_text_input(
                "利用終了日",
                form.get("service_end_date") or "",
                prefix + "service_end_date",
                common,
            )
            _copyable_number_input(
                "金額",
                float(form.get("amount") or 0),
                prefix + "amount",
                common,
            )
            _copyable_text_input(
                "決裁科目番号",
                form.get("approval_category_no", ""),
                prefix + "approval_category_no",
                common,
            )
            _copyable_text_area(
                "決裁本文",
                form.get("body", ""),
                prefix + "body",
                common,
            )
            st.session_state[prefix + "required_documents"] = form.get("required_documents", [])
            current_form = _current_form_from_state(case_id, form)
            if message := st.session_state.pop("autosave_message", None):
                st.caption(message)

    st.markdown(
        '<div class="app-section-heading">結果確認</div>',
        unsafe_allow_html=True,
    )
    _render_confirmation_summary(case, current_form)

    with st.expander("🧾 要約・書類比較・不足確認を表示", expanded=False):
        st.markdown("#### 生成内容")
        st.write(case.get("summary") or "要約はありません。")

        st.markdown("#### 書類間の記載内容比較")
        comparison_rows = build_comparison_rows(case, current_form)
        if comparison_rows:
            st.dataframe(
                comparison_rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "確認項目": st.column_config.TextColumn(width="small"),
                    "AI決裁フォーム": st.column_config.TextColumn(width="medium"),
                    "書類": st.column_config.TextColumn(width="small"),
                    "書類記載値": st.column_config.TextColumn(width="medium"),
                    "照合結果": st.column_config.TextColumn(width="small"),
                },
            )
        else:
            st.info("比較できる添付書類がありません。")

        st.markdown("#### ⚠ 不足・注意")
        if message := st.session_state.pop("document_recovery_message", None):
            st.success(message)
        for item in case.get("resolution_notices", []):
            st.success(item["message"])
        for item in case.get("validation_results", []):
            renderer = {
                "error": st.error,
                "warning": st.warning,
                "info": st.info,
                "success": st.success,
            }[item["severity"]]
            renderer(item["message"])
        _render_document_recovery(client, case)

        st.markdown("#### ✅ チェックリスト")
        st.caption("フォームと添付書類を照合し、確認済みにできる項目をAIで判定します。")
        _render_checklist(client, case)

        st.markdown("#### 📚 必要書類")
        documents = current_form.get("required_documents", [])
        st.write("、".join(documents) if documents else "AIが必要書類を特定できませんでした。")

    with st.expander("詳細情報", expanded=False):
        st.markdown("#### 類似決裁")
        similar = case.get("similar_cases", [])
        if not similar:
            st.info("直接類似する過去決裁は見つかりませんでした。基準資料を優先して作成しています。")
        for index, item in enumerate(similar, start=1):
            with st.container(border=True):
                st.markdown(f"**参考候補 {index}: {item['title']}**")
                st.write(item["reason"])
                details = []
                if item.get("approval_category_no"):
                    details.append(f"決裁科目番号: {item['approval_category_no']}")
                if item.get("amount") is not None:
                    details.append(f"金額: {item['amount']:,.0f}円")
                if details:
                    st.caption(" / ".join(details))

        st.markdown("#### 修正履歴")
        for version in reversed(case.get("versions", [])):
            st.markdown(f"**Version {version['version']} · {_format_datetime(version.get('created_at'))}**")
            st.write(case.get("title") or "決裁案")
            instruction = version.get("instruction", "")
            st.caption("AI決裁案を初回作成" if instruction == "initial_generation" else instruction)
            st.divider()

    st.markdown(
        '<div class="app-section-heading">AIチャット</div>',
        unsafe_allow_html=True,
    )
    st.caption("自然文で依頼すると、AIが対象項目を判断して必要な箇所だけへ反映します。")
    input_version_key = f"revision_input_version_{case_id}"
    input_version = st.session_state.get(input_version_key, 0)
    instruction_key = f"revision_instruction_{case_id}_{input_version}"

    chat_logs = case.get("chat_logs", [])
    with st.container(border=True):
        recent_logs = chat_logs[-6:]
        if recent_logs:
            _render_revision_logs(recent_logs)
        older_logs = chat_logs[:-len(recent_logs)]
        if older_logs:
            with st.expander(f"過去の修正履歴を表示（{len(older_logs) // 2}件）"):
                _render_revision_logs(older_logs)

        with st.form(f"revision_form_{case_id}", clear_on_submit=False):
            instruction = st.text_area(
                "AIへの依頼内容",
                placeholder="例: 決裁本文を承認者向けに1文へまとめてください。金額と期間も添付書類と再確認してください。",
                key=instruction_key,
            )
            submitted = st.form_submit_button(
                "💬 AIに相談・修正",
                type="primary",
                use_container_width=True,
            )

    if submitted:
        if not instruction.strip():
            st.warning("修正内容を入力してください。")
            return
        try:
            with st.chat_message("user"):
                st.write(instruction.strip())
            with st.chat_message("assistant"):
                with st.spinner("最新案を作成しています"):
                    st.write("最新案を作成しています。")
                    client.chat(
                        case_id,
                        instruction.strip(),
                        "all",
                    )
            _clear_form_state(case_id)
            st.session_state[input_version_key] = input_version + 1
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))
