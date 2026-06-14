from pathlib import Path

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
        st.caption("基準資料は1件ずつ登録します。登録後、次の資料を選択してください。")
        with st.form("material_registration", clear_on_submit=True):
            category_label = st.selectbox("対象カテゴリ", list(CATEGORIES), key="material_category")
            approval_type = st.selectbox("対象決裁種類", APPROVAL_TYPES, key="material_type")
            knowledge_type = st.radio(
                "資料種別",
                ["policy", "template", "required_document_rule", "past_case"],
                horizontal=True,
                format_func={
                    "policy": "決裁規程",
                    "template": "標準様式",
                    "required_document_rule": "必要書類基準",
                    "past_case": "サンプル過去決裁",
                }.get,
            )
            title = st.text_input("資料タイトル（未入力時はファイル名を使用）")
            material = st.file_uploader("基準資料", type=["pdf", "md", "txt"])
            register = st.form_submit_button(
                "資料を登録",
                type="primary",
            )
        if register:
            if material is None:
                st.error("登録する基準資料を選択してください。")
                return
            try:
                resolved_title = title.strip() or Path(material.name).stem
                client.upload_material(
                    {
                        "business_category": CATEGORIES[category_label],
                        "approval_type": approval_type,
                        "knowledge_type": knowledge_type,
                        "title": resolved_title,
                    },
                    material,
                )
                st.success("資料を登録しました。")
            except ApiError as exc:
                st.error(str(exc))
        reindex_slot = st.empty()
        if reindex_slot.button("検索インデックスを更新", key="reindex_materials"):
            reindex_slot.empty()
            try:
                with st.status("検索インデックスを更新しています", expanded=True) as status:
                    st.write("登録済みの基準資料と過去決裁をAzure AI Searchへ送信しています。")
                    result = client.reindex()
                    status.update(label="検索インデックスを更新しました", state="complete", expanded=False)
                if result.get("mode") == "azure":
                    st.success(f"{result['indexed']}件をAzure AI Searchへ登録しました。")
                else:
                    st.info(
                        f"Local mode: 検索対象{result['indexed']}件を確認しました。"
                        "Azure AI Searchへは送信されていません。"
                    )
            except ApiError as exc:
                st.error(str(exc))

    with tab_connection:
        st.caption("この情報は初期設定画面だけに表示します。")
        try:
            result = client.dependency_health()
            if result.get("mode") == "local":
                st.info(
                    "現在はLocal modeです。データはローカルに保存され、"
                    "Azure Blob Storage、AI Search、Cosmos DB、Azure OpenAIは使用しません。"
                )
            for name, status in result["checks"].items():
                if status["status"] == "ok":
                    suffix = "ローカル動作中" if result.get("mode") == "local" else "接続済み"
                    st.success(f"{name}: {suffix}")
                elif status["status"] == "skipped":
                    st.warning(f"{name}: {status.get('message', '未使用')}")
                else:
                    st.error(f"{name}: {status.get('message', '接続エラー')}")
                details = status.get("details", {})
                if name == "blob" and details:
                    st.caption(
                        f"Storage account: {details.get('storage_account') or '-'} / "
                        f"Containers: {', '.join(details.get('containers', []))}"
                    )
                elif name == "search" and details:
                    st.caption(
                        f"Index: {details.get('index') or '-'} / "
                        "登録方式: アプリケーションからSDKで直接登録"
                    )
                    st.caption("Indexer・Data source・Skillsetはこの方式では作成しません。")
                elif name == "cosmos" and details:
                    st.caption(f"履歴・設定の保存先: {details.get('database') or '-'}")
        except ApiError as exc:
            st.error(str(exc))
