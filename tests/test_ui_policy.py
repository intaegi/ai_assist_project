from pathlib import Path


def test_new_case_has_single_primary_action():
    source = Path("frontend/components/new_case_page.py").read_text(encoding="utf-8")
    assert source.count('st.button("✨ AI決裁案を作成"') == 1
    assert "NEW REQUEST" not in source
    assert "一時保存" not in source
    assert "作成完了" not in source
    assert '<h1 class="page-title">新規決裁作成</h1>' in source
    assert "📋 作成前の準備事項" in source
    assert "□ 作成前の準備事項" not in source


def test_result_uses_revision_form_and_chat_history_without_save_button():
    source = Path("frontend/components/result_page.py").read_text(encoding="utf-8")
    assert "st.chat_input" not in source
    assert "st.form(" in source
    assert "st.form_submit_button(" in source
    assert "clear_on_submit=False" in source
    assert "修正チャット履歴" not in source
    assert "st.chat_message(" in source
    assert "登録済みのためスキップしました" in source
    assert "追加書類を1件以上選択してください。" in source
    assert "disabled=not files" not in source
    assert "revision_success_message" not in source
    assert "過去の修正履歴を表示" in source
    assert 'st.expander("🧾 要約・書類比較・不足確認を表示", expanded=False)' in source
    assert 'st.tabs(["要約"' not in source
    assert 'st.expander("詳細情報"' in source
    assert "フォーム内容をコピー" in source
    assert "_render_field_copy_button" in source
    assert "タイトルをコピー" not in source
    assert '<svg viewBox="0 0 24 24"' in source
    assert 'role="tooltip"' not in source
    assert "フォームコピー" in source
    assert "AI DRAFT" not in source
    assert "height=120" in source
    assert "build_comparison_rows" in source
    assert "生成結果表示" in source
    assert "result-pair-marker" in source
    assert 'st.columns([4, 6], gap="small")' in source
    assert "結果確認" in source
    assert "AIチャット" in source
    assert "不足書類を追加して再確認" in source
    assert "書類を追加して再確認" in source
    assert "チェックリストをAIで確認" in source
    assert "resolution_notices" in source
    assert "_clear_form_state" in source
    assert 'key=f"revision_target_{case_id}"' not in source
    assert '"all"' in source
    assert "AIへの依頼内容" in source
    assert "自然文で依頼すると、AIが対象項目を判断" in source
    assert "変更内容を保存" not in source
    assert "作成完了" not in source
    assert "_copyable_number_input" in source
    assert 'st.columns([4.8, 0.8, 4.8, 0.8]' not in source


def test_chat_message_colors_are_role_specific():
    source = Path("frontend/app.py").read_text(encoding="utf-8")
    assert 'chatAvatarIcon-user' in source
    assert 'chatAvatarIcon-assistant' in source
    assert 'div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"])' in source
    assert 'background: var(--app-soft);' in source
    assert 'div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"])' in source
    assert 'background: #fff;' in source


def test_streamlit_entrypoint_adds_project_root_to_python_path():
    source = Path("frontend/app.py").read_text(encoding="utf-8")
    assert "Path(__file__).resolve().parents[1]" in source
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in source


def test_streamlit_theme_uses_accent_primary_color():
    source = Path(".streamlit/config.toml").read_text(encoding="utf-8")
    assert 'primaryColor = "#7C3AED"' in source
    assert 'backgroundColor = "#FFFFFF"' in source
    assert 'toolbarMode = "minimal"' in source


def test_material_registration_is_single_item_and_clears_form():
    source = Path("frontend/components/settings_page.py").read_text(encoding="utf-8")
    assert 'st.form("material_registration", clear_on_submit=True)' in source
    assert 'knowledge_type = st.radio(' in source
    assert '"template": "標準様式"' in source
    assert "disabled=material is None" not in source
    assert "登録する基準資料を選択してください。" in source
    assert "Path(material.name).stem" in source
    assert "Azure AI Searchへは送信されていません" in source
    assert "検索結果が古い場合" in source
    assert "毎回押す必要はありません" in source
    assert "🔄 検索インデックスを手動更新" in source


def test_settings_labels_explain_rule_formats():
    source = Path("frontend/components/settings_page.py").read_text(encoding="utf-8")
    assert "app-page-kicker" not in source
    assert '<h1 class="page-title">初期設定</h1>' in source
    assert "必須入力項目（1行につき キー|表示名|入力型）" in source
    assert "条件付き書類（1行につき 書類名|条件）" in source
    assert "キーは内部ID、表示名はAI生成フォームの項目名" in source
    assert "保存後、この設定はAI生成フォームの抽出項目" in source
    assert "条件に該当すると、該当書類が不足していないか" in source


def test_sidebar_marks_current_page_as_primary():
    source = Path("frontend/components/sidebar.py").read_text(encoding="utf-8")
    assert 'type="primary" if page == "settings" else "secondary"' in source
    assert 'type="primary" if page == "new" else "secondary"' in source
    assert "on_click=_select_new_page" in source
    assert "on_click=_select_settings_page" in source
    assert "📝 新規作成" in source
    assert "⚙️ 初期設定" in source
    assert "history_show_more" in source
    assert "history-icon" not in source
    assert 'st.query_params.get("case_id")' in source
    assert 'class="history-item{active_class}"' in source
    assert 'class="history-title"' in source
    assert 'class="history-time"' in source
    assert "history-more-button-marker" in source
    assert "▾ もっと見る" in source
    assert 'href = "?case_id=' not in source
    assert 'st.rerun()' not in source


def test_global_css_keeps_settings_inputs_and_history_readable():
    source = Path("frontend/app.py").read_text(encoding="utf-8")
    assert '[data-testid="stSidebar"] div[data-testid="stButton"] button p' in source
    assert "white-space: pre-line;" in source
    assert ".page-title" in source
    assert "font-weight: 700 !important;" in source
    assert "history-more-button-marker" in source
    assert "button:focus-visible" in source
    assert 'button[data-baseweb="tab"] p' in source
    assert 'div[data-testid="stTextArea"] textarea' in source
    assert 'div[data-testid="stFileUploader"] section' in source


def test_frontend_health_check_uses_short_timeout():
    source = Path("frontend/api_client.py").read_text(encoding="utf-8")
    assert 'return self._request("GET", "/health", timeout=5)' in source


def test_frontend_warns_when_backend_is_stale():
    source = Path("frontend/app.py").read_text(encoding="utf-8")
    assert '"checklist_verification" not in' in source
    assert "FastAPIが旧バージョンで起動しています" in source
