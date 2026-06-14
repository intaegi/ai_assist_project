from pathlib import Path


def test_new_case_has_single_primary_action():
    source = Path("frontend/components/new_case_page.py").read_text(encoding="utf-8")
    assert source.count('st.button("AI決裁案を作成"') == 1
    assert "一時保存" not in source
    assert "作成完了" not in source


def test_result_uses_chat_input_without_save_button():
    source = Path("frontend/components/result_page.py").read_text(encoding="utf-8")
    assert "st.chat_input" in source
    assert 'st.subheader("要約")' in source
    assert 'st.tabs(["要約"' not in source
    assert 'st.expander("詳細情報"' in source
    assert "フォーム内容をコピー" in source
    assert "build_comparison_rows" in source
    assert "変更内容を保存" not in source
    assert "作成完了" not in source


def test_streamlit_entrypoint_adds_project_root_to_python_path():
    source = Path("frontend/app.py").read_text(encoding="utf-8")
    assert "Path(__file__).resolve().parents[1]" in source
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in source


def test_streamlit_theme_uses_blue_primary_color():
    source = Path(".streamlit/config.toml").read_text(encoding="utf-8")
    assert 'primaryColor = "#1769AA"' in source


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
