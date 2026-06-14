import json

from backend.app.services.storage import LocalBlobStore, LocalDataStore


def test_local_store_compacts_duplicate_materials_on_startup(tmp_path):
    database = tmp_path / "database.json"
    duplicate = {
        "id": "material-1",
        "business_category": "it",
        "approval_type": "支払",
        "knowledge_type": "policy",
        "title": "最新版",
    }
    database.write_text(
        json.dumps(
            {
                "cases": {},
                "requirements": [],
                "materials": [{**duplicate, "title": "旧版"}, duplicate],
                "past_decisions": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    store = LocalDataStore(tmp_path)

    assert store.list_materials() == [duplicate]
    saved = json.loads(database.read_text(encoding="utf-8"))
    assert saved["materials"] == [duplicate]


def test_local_blob_store_syncs_search_documents_and_removes_stale_files(tmp_path):
    store = LocalBlobStore(tmp_path)
    stale = tmp_path / "files" / "search-knowledge" / "documents" / "stale.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")

    count = store.sync_json_documents(
        "search-knowledge",
        "documents",
        [{"id": "policy-1", "title": "支払規程", "content": "10万円以上"}],
    )

    files = list(stale.parent.glob("*.json"))
    assert count == 1
    assert len(files) == 1
    assert files[0].name != "stale.json"
    assert json.loads(files[0].read_text(encoding="utf-8"))["title"] == "支払規程"
