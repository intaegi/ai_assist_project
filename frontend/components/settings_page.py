import streamlit as st

from frontend.api_client import ApiError


CATEGORIES = {"営業": "sales", "経理・購買": "finance", "開発・IT": "it", "その他": "other"}
APPROVAL_TYPES = ["購入", "支払", "契約", "出張・イベント", "その他"]


def render_settings_page(client) -> None:
    st.title("初期設定")
    st.caption("決裁カテゴリごとの必須入力項目、必要書類、RAG基準資料を登録します。")

    tab_rules, tab_materials, tab_connection = st.tabs(["入力・書類基準", "基準資料", "接続確認"])
    with tab_rules:
        category_label = st.selectbox("業務カテゴリ", list(CATEGORIES))
        approval_type = st.selectbox("決裁種類", APPROVAL_TYPES)
        required_fields = st.text_area(
            "必須入力項目（1行につき `キー|表示名|入力型`）",
            "purpose|目的|textarea\nvendor|取引先|text\nservice_name|製品・サービス名|text\namount|金額|number",
            height=140,
        )
        required_documents = st.text_input("必要書類（カンマ区切り）", "請求書")
        conditional_documents = st.text_area(
            "条件付き書類（1行につき `書類名|条件`）",
            "見積書|新規契約または10万円以上の場合",
            height=90,
        )
        if st.button("基準設定を保存", type="primary"):
            fields = []
            for line in required_fields.splitlines():
                parts = [part.strip() for part in line.split("|")]
                if len(parts) == 3:
                    fields.append({"key": parts[0], "label": parts[1], "type": parts[2], "required": True})
            conditional = []
            for line in conditional_documents.splitlines():
                parts = [part.strip() for part in line.split("|", 1)]
                if len(parts) == 2:
                    conditional.append({"document": parts[0], "condition": parts[1]})
            payload = {
                "business_category": CATEGORIES[category_label],
                "approval_type": approval_type,
                "required_fields": fields,
                "required_documents": [item.strip() for item in required_documents.split(",") if item.strip()],
                "conditional_documents": conditional,
                "form_template": {"body_sections": [field["label"] for field in fields]},
            }
            try:
                client.save_requirement(payload)
                st.success("基準設定を保存しました。")
            except ApiError as exc:
                st.error(str(exc))

    with tab_materials:
        category_label = st.selectbox("対象カテゴリ", list(CATEGORIES), key="material_category")
        approval_type = st.selectbox("対象決裁種類", APPROVAL_TYPES, key="material_type")
        knowledge_type = st.selectbox(
            "資料種別",
            ["policy", "template", "required_document_rule", "past_case"],
            format_func={
                "policy": "決裁規程",
                "template": "標準様式",
                "required_document_rule": "必要書類基準",
                "past_case": "サンプル過去決裁",
            }.get,
        )
        title = st.text_input("資料タイトル")
        material = st.file_uploader("基準資料", type=["pdf", "md", "txt"])
        if st.button("資料を登録", disabled=not title or material is None):
            try:
                client.upload_material(
                    {
                        "business_category": CATEGORIES[category_label],
                        "approval_type": approval_type,
                        "knowledge_type": knowledge_type,
                        "title": title,
                    },
                    material,
                )
                st.success("資料を登録しました。")
            except ApiError as exc:
                st.error(str(exc))
        if st.button("検索インデックスを更新"):
            try:
                result = client.reindex()
                st.success(f"{result['indexed']}件をインデックスへ登録しました。")
            except ApiError as exc:
                st.error(str(exc))

    with tab_connection:
        st.caption("この情報は初期設定画面だけに表示します。")
        try:
            result = client.dependency_health()
            for name, status in result["checks"].items():
                if status["status"] == "ok":
                    st.success(f"{name}: 接続済み")
                else:
                    st.error(f"{name}: {status.get('message', '接続エラー')}")
        except ApiError as exc:
            st.error(str(exc))
