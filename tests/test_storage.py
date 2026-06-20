import json

from backend.app.services.storage import AzureBlobStore, LocalBlobStore, LocalDataStore


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
    stale = tmp_path / "files" / "lim-pbl-search-knowledge" / "documents" / "stale.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")

    count = store.sync_json_documents(
        "lim-pbl-search-knowledge",
        "documents",
        [{"id": "policy-1", "title": "支払規程", "content": "10万円以上"}],
    )

    files = list(stale.parent.glob("*.json"))
    assert count == 1
    assert len(files) == 1
    assert files[0].name != "stale.json"
    assert json.loads(files[0].read_text(encoding="utf-8"))["title"] == "支払規程"


def test_azure_blob_store_creates_missing_container_before_upload():
    class FakeContainer:
        def __init__(self):
            self.exists_value = False
            self.create_count = 0

        def exists(self):
            return self.exists_value

        def create_container(self):
            self.exists_value = True
            self.create_count += 1

    class FakeBlob:
        def __init__(self):
            self.uploads = []

        def upload_blob(self, content, overwrite, content_settings):
            self.uploads.append((content, overwrite, content_settings.content_type))

    class FakeClient:
        def __init__(self):
            self.container = FakeContainer()
            self.blob = FakeBlob()

        def get_container_client(self, container):
            assert container == "generated-outputs"
            return self.container

        def get_blob_client(self, container, blob):
            assert container == "generated-outputs"
            assert blob == "cases/case-1/versions/1.json"
            return self.blob

    store = object.__new__(AzureBlobStore)
    store.client = FakeClient()
    store._known_containers = set()

    store.upload("generated-outputs", "cases/case-1/versions/1.json", b"{}", "application/json")
    store.upload("generated-outputs", "cases/case-1/versions/1.json", b"{}", "application/json")

    assert store.client.container.create_count == 1
    assert len(store.client.blob.uploads) == 2
