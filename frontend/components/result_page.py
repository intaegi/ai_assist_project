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

REVISION_TARGETS = {
    "決裁本文": "body",
    "決裁フォーム全体": "form",
    "決裁案全体（フォーム・要約・チェックリスト）": "all",
    "タイトル": "title",
    "取引先": "vendor",
    "製品・サービス名": "service_name",
    "利用期間": "service_period",
    "金額": "amount",
    "決裁科目番号": "approval_category_no",
}


def _revision_target_label(target_field: str) -> str:
    return next(
        (
            label
            for label, value in REVISION_TARGETS.items()
            if value == target_field
        ),
        target_field,
    )


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


def _render_copy_button(form: dict) -> None:
    text = json.dumps(_form_copy_text(form), ensure_ascii=False).replace("</", "<\\/")
    components.html(
        f"""
        <button id="copy-form" type="button">フォーム内容をコピー</button>
        <span id="copy-result" aria-live="polite"></span>
        <script>
          const button = document.getElementById("copy-form");
          const result = document.getElementById("copy-result");
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
            result.textContent = "コピーしました";
          }});
        </script>
        <style>
          body {{ margin: 0; font-family: sans-serif; }}
          button {{
            min-height: 38px;
            padding: 0 14px;
            border: 1px solid #1769aa;
            border-radius: 6px;
            color: #1769aa;
            background: #fff;
            cursor: pointer;
          }}
          button:hover {{ background: #eef6fb; }}
          span {{ margin-left: 10px; color: #17603a; font-size: 13px; }}
        </style>
        """,
        height=48,
    )


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

    with st.container(border=True):
        st.markdown("##### 不足書類を追加して再確認")
        if missing_names:
            st.caption("現在不足している書類: " + "、".join(missing_names))
        files = st.file_uploader(
            "追加書類",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key=f"recovery_files_{case['case_id']}",
        )
        instruction = st.text_area(
            "AIへの反映指示",
            value="追加した書類の内容を確認し、決裁フォーム、要約、チェックリストを更新してください。",
            height=90,
            key=f"recovery_instruction_{case['case_id']}",
        )
        regenerate = st.checkbox(
            "追加書類を反映してAI決裁案を再作成する",
            value=True,
            key=f"recovery_regenerate_{case['case_id']}",
        )
        if st.button(
            "書類を追加して再確認",
            type="primary",
            use_container_width=True,
            disabled=not files,
            key=f"recovery_submit_{case['case_id']}",
        ):
            try:
                with st.status("追加書類を確認しています", expanded=True) as status:
                    for file in files or []:
                        st.write(f"{file.name} を保存しています")
                        client.add_file(case["case_id"], file)
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
                st.session_state["document_recovery_message"] = (
                    "追加書類を保存し、不足・注意とチェックリストを再確認しました。"
                )
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))


def _render_checklist(client, case: dict) -> None:
    checklist = case.get("checklist", [])
    if not checklist:
        st.caption("確認項目はありません。")
        return

    if st.button(
        "チェックリストをAIで確認",
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


def render_result_page(client, case_id: str, history_mode: bool = False) -> None:
    try:
        case = client.get_case(case_id)
    except ApiError as exc:
        st.error(str(exc))
        return
    title = case.get("title") or "決裁案"
    st.title(title)
    st.caption(f"最終更新: {_format_datetime(case.get('updated_at'))}")
    copy_clicked = False
    if history_mode:
        _, copy_col = st.columns([4, 1.5])
        copy_clicked = copy_col.button("新規作成へコピー", use_container_width=True)
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

    preview_col, form_col = st.columns([1.05, 1], gap="large")
    with preview_col:
        st.subheader("原本書類")
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
        current_form = {
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
        _render_copy_button(current_form)
        if message := st.session_state.pop("autosave_message", None):
            st.caption(message)

    st.subheader("要約")
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

    st.markdown("#### 不足・注意")
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

    st.markdown("#### チェックリスト")
    _render_checklist(client, case)

    st.markdown("#### 必要書類")
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

    st.markdown("---")
    st.subheader("AIへの修正依頼")
    chat_logs = case.get("chat_logs", [])
    if chat_logs:
        st.markdown("#### 修正チャット履歴")
        for log in chat_logs:
            role = log.get("role", "assistant")
            with st.chat_message(role if role in {"user", "assistant"} else "assistant"):
                target = _revision_target_label(log.get("target_field", ""))
                if target:
                    st.caption(f"修正対象: {target}")
                st.write(log.get("message", ""))

    with st.form(f"revision_form_{case_id}", clear_on_submit=True):
        target_label = st.selectbox(
            "修正対象",
            list(REVISION_TARGETS),
            key=f"revision_target_{case_id}",
        )
        instruction = st.text_area(
            "修正内容",
            placeholder="例: 決裁本文を承認者向けに1文へまとめてください。",
            key=f"revision_instruction_{case_id}",
        )
        submitted = st.form_submit_button(
            "AIに修正を依頼",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not instruction.strip():
            st.warning("修正内容を入力してください。")
            return
        try:
            with st.spinner("最新案を作成しています"):
                client.chat(
                    case_id,
                    instruction.strip(),
                    REVISION_TARGETS[target_label],
                )
            _clear_form_state(case_id)
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))
