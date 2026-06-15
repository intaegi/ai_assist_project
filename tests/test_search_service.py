from unittest.mock import MagicMock

from azure.search.documents.indexes.models import SearchField, SearchFieldDataType, SearchIndex

from backend.app.core.config import Settings
from backend.app.services.search_service import AzureSearchService


def _azure_settings(**overrides):
    values = {
        "_env_file": None,
        "azure_search_endpoint": "https://example.search.windows.net",
        "azure_search_api_key": "test",
        "azure_storage_connection_string": "UseDevelopmentStorage=true",
        "azure_openai_endpoint": "https://example.openai.azure.com",
        "azure_openai_api_key": "test",
        "azure_openai_embedding_deployment": "embedding",
        "azure_search_index_name": "test-index",
        "azure_search_indexer_name": "test-indexer",
        "azure_search_ingestion_mode": "indexer",
    }
    values.update(overrides)
    return Settings(**values)


def test_indexer_mode_stages_documents_and_runs_indexer():
    blob_store = MagicMock()
    blob_store.sync_json_documents.return_value = 2
    service = AzureSearchService(_azure_settings(), lambda _: [0.0], blob_store)
    service.indexer_client = MagicMock()
    documents = [
        {"id": "policy-1", "content": "policy"},
        {"id": "past-1", "content": "past decision"},
    ]

    count = service.index_documents(documents)

    assert count == 2
    blob_store.sync_json_documents.assert_called_once_with(
        "lim-pbl-search-knowledge",
        "documents",
        [
            {"id": "policy-1", "source_id": "policy-1", "content": "policy"},
            {"id": "past-1", "source_id": "past-1", "content": "past decision"},
        ],
    )
    service.indexer_client.run_indexer.assert_called_once_with("test-indexer")


def test_direct_mode_keeps_push_upload_as_fallback():
    service = AzureSearchService(
        _azure_settings(azure_search_ingestion_mode="direct"),
        lambda _: [0.25, 0.75],
    )
    service.client = MagicMock()

    count = service.index_documents([{"id": "policy-1", "content": "policy"}])

    assert count == 1
    uploaded = service.client.upload_documents.call_args.args[0][0]
    assert uploaded["source_id"] == "policy-1"
    assert uploaded["content_vector"] == [0.25, 0.75]


def test_indexer_schema_rebuilds_legacy_direct_upload_index():
    legacy = SearchIndex(
        name="test-index",
        fields=[
            SearchField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=1536,
                vector_search_profile_name="decision-vector-profile",
            ),
        ],
    )

    assert AzureSearchService._index_requires_rebuild(legacy, 1536) is True
