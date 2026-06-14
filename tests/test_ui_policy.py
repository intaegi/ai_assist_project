from pathlib import Path


def test_new_case_has_single_primary_action():
    source = Path("frontend/components/new_case_page.py").read_text(encoding="utf-8")
    assert source.count('st.button("AI決裁案を作成"') == 1
    assert "一時保存" not in source
    assert "作成完了" not in source


def test_result_uses_chat_input_without_save_button():
    source = Path("frontend/components/result_page.py").read_text(encoding="utf-8")
    assert "st.chat_input" in source
    assert "変更内容を保存" not in source
    assert "作成完了" not in source


def test_streamlit_entrypoint_adds_project_root_to_python_path():
    source = Path("frontend/app.py").read_text(encoding="utf-8")
    assert "Path(__file__).resolve().parents[1]" in source
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in source
