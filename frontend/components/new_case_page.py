import json

import streamlit as st

from frontend.api_client import ApiError


CATEGORIES = {"営業": "sales", "経理・購買": "finance", "開発・IT": "it", "その他": "other"}
APPROVAL_TYPES = ["購入", "支払", "契約", "出張・イベント", "その他"]


def render_new_case_page(client) -> str | None:
    st.markdown(
        '<div class="app-page-kicker">NEW REQUEST</div>',
        unsafe_allow_html=True,
    )
    st.title("新規決裁作成")
    st.caption("目的と添付書類をもとに、AIが決裁フォーム・要約・チェックリストを作成します。")
    clone = st.session_state.get("draft_clone")
    reverse_categories = {value: key for key, value in CATEGORIES.items()}
    default_category = reverse_categories.get((clone or {}).get("business_category"), "開発・IT")
    category_label = st.radio(
        "業務カテゴリ",
        list(CATEGORIES),
        index=list(CATEGORIES).index(default_category),
        horizontal=True,
    )
    category = CATEGORIES[category_label]
    category_other = (
        st.text_input("その他のカテゴリ名", value=(clone or {}).get("business_category_other") or "")
        if category == "other"
        else ""
    )
    default_type = (clone or {}).get("approval_type", "支払")
    type_index = APPROVAL_TYPES.index(default_type) if default_type in APPROVAL_TYPES else 0
    approval_type = st.selectbox("決裁種類", APPROVAL_TYPES, index=type_index)
    approval_type_other = (
        st.text_input("その他の決裁種類", value=(clone or {}).get("approval_type_other") or "")
        if approval_type == "その他"
        else ""
    )

    try:
        requirement = client.requirements(category, approval_type)
    except ApiError:
        requirement = {"source_status": "no_reference", "required_fields": [], "required_documents": [], "conditional_documents": []}

    with st.container(border=True):
        st.subheader("□ 作成前の準備事項")
        if requirement.get("source_status") == "no_reference":
            st.warning("このカテゴリには社内基準と過去事例が登録されていません。担当部門への確認が必要です。")
        fields = requirement.get("required_fields", [])
        labels = [item["label"] if isinstance(item, dict) else str(item) for item in fields]
        st.write("**必須記載:** " + ("、".join(labels) if labels else "目的、取引先、製品・サービス、金額"))
        documents = requirement.get("required_documents", [])
        st.write("**必要書類:** " + ("、".join(documents) if documents else "登録された必須書類なし"))
        for item in requirement.get("conditional_documents", []):
            st.caption(f"条件付き: {item['document']} - {item['condition']}")

    if clone:
        st.info("過去履歴からコピーしました。日付、金額、利用期間、添付書類を再確認してください。")
        if clone.get("files"):
            st.caption("コピー済み書類: " + "、".join(file["file_name"] for file in clone["files"]))
    title = st.text_input("決裁タイトル（任意）", value=(clone or {}).get("title", ""))
    description = st.text_area(
        "決裁目的と必要な内容",
        value=(clone or {}).get("description", ""),
        placeholder="例: 開発チームで利用するクラウドサービスの年間利用料を支払います。",
        height=130,
    )
    col1, col2, col3 = st.columns(3)
    approval_category_no = col1.text_input(
        "決裁科目番号（任意）",
        value=(clone or {}).get("approval_category_no", ""),
    )
    amount = col2.number_input(
        "予定金額（任意）",
        min_value=0.0,
        step=1000.0,
        value=float((clone or {}).get("amount") or 0),
    )
    approval_no = col3.text_input("決裁番号（任意）", value="")
    uploaded_files = st.file_uploader(
        "関連書類",
        type=["pdf", "jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )
    disabled = not description.strip() or (category == "other" and not category_other.strip())
    if st.button("✨ AI決裁案を作成", type="primary", use_container_width=True, disabled=disabled):
        data = {
            "business_category": category,
            "business_category_other": category_other,
            "approval_type": approval_type,
            "approval_type_other": approval_type_other,
            "title": title,
            "description": description,
            "approval_no": approval_no,
            "approval_category_no": approval_category_no,
            "requester_id": "demo-user",
            "category_fields": json.dumps({}, ensure_ascii=False),
        }
        if amount > 0:
            data["amount"] = amount
        try:
            with st.status("AI決裁案を作成しています", expanded=True) as status:
                if clone:
                    st.write("コピーした案件と追加ファイルを更新しています")
                    case = client.patch_case(
                        clone["case_id"],
                        {
                            "business_category": category,
                            "business_category_other": category_other or None,
                            "approval_type": approval_type,
                            "approval_type_other": approval_type_other or None,
                            "description": description,
                            "title": title,
                            "approval_no": approval_no,
                            "approval_category_no": approval_category_no,
                            "amount": amount if amount > 0 else None,
                        },
                    )
                    for file in uploaded_files or []:
                        case = client.add_file(case["case_id"], file)
                else:
                    st.write("ファイルを保存しています")
                    case = client.create_case(data, uploaded_files or [])
                st.write("文書を解析し、基準と類似事例を検索しています")
                result = client.generate(case["case_id"])
                status.update(label="決裁案を作成しました", state="complete", expanded=False)
            st.session_state.pop("draft_clone", None)
            st.session_state.case_id = result["case_id"]
            st.session_state.page = "result"
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))
    return None
