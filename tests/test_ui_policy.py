from pathlib import Path


def test_new_case_has_single_primary_action():
    source = Path("frontend/components/new_case_page.py").read_text(encoding="utf-8")
    assert source.count('st.button("AI決裁案を作成"') == 1
    assert "一時保存" not in source
    assert "作成完了" not in source


def test_result_uses_revision_form_and_chat_history_without_save_button():
    source = Path("frontend/components/result_page.py").read_text(encoding="utf-8")
    assert "st.chat_input" not in source
    assert "st.form(" in source
    assert "st.form_submit_button(" in source
    assert "clear_on_submit=False" in source
    assert "修正チャット履歴" in source
    assert "st.chat_message(" in source
    assert "登録済みのためスキップしました" in source
    assert "追加書類を1件以上選択してください。" in source
    assert "disabled=not files" not in source
    assert "revision_success_message" in source
    assert "過去の修正履歴を表示" in source
    assert 'st.subheader("要約")' in source
    assert 'st.tabs(["要約"' not in source
    assert 'st.expander("詳細情報"' in source
    assert "フォーム内容をコピー" in source
    assert "_render_field_copy_button" in source
    assert "タイトルをコピー" not in source
    assert '<svg viewBox="0 0 24 24"' in source
    assert 'if compact' in source
    assert "build_comparison_rows" in source
    assert "不足書類を追加して再確認" in source
    assert "書類を追加して再確認" in source
    assert "チェックリストをAIで確認" in source
    assert "resolution_notices" in source
    assert "_clear_form_state" in source
    assert "決裁フォーム全体" in source
    assert "決裁案全体（フォーム・要約・チェックリスト）" in source
    assert "変更内容を保存" not in source
    assert "作成完了" not in source


def test_streamlit_entrypoint_adds_project_root_to_python_path():
    source = Path("frontend/app.py").read_text(encoding="utf-8")
    assert "Path(__file__).resolve().parents[1]" in source
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in source


def test_streamlit_theme_uses_accent_primary_color():
    source = Path(".streamlit/config.toml").read_text(encoding="utf-8")
    assert 'primaryColor = "#0AB4F7"' in source
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


def test_sidebar_marks_current_page_as_primary():
    source = Path("frontend/components/sidebar.py").read_text(encoding="utf-8")
    assert 'type="primary" if page == "settings" else "secondary"' in source
    assert 'class="history-item{active_class}"' in source
    assert 'class="history-time"' in source
    assert 'st.query_params.get("case_id")' in source


def test_frontend_health_check_uses_short_timeout():
    source = Path("frontend/api_client.py").read_text(encoding="utf-8")
    assert 'return self._request("GET", "/health", timeout=5)' in source


def test_frontend_warns_when_backend_is_stale():
    source = Path("frontend/app.py").read_text(encoding="utf-8")
    assert '"checklist_verification" not in' in source
    assert "FastAPIが旧バージョンで起動しています" in source
