from backend.app.core.config import Settings


def test_cosmos_can_be_deferred_in_azure_mode():
    settings = Settings(
        app_storage_mode="azure",
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_api_key="test",
        azure_openai_chat_deployment="chat",
        azure_openai_embedding_deployment="embedding",
        azure_search_endpoint="https://example.search.windows.net",
        azure_search_api_key="test",
        azure_storage_connection_string="UseDevelopmentStorage=true",
        azure_cosmos_enabled=False,
    )

    assert settings.missing_azure_settings() == []


def test_cosmos_is_required_when_enabled():
    settings = Settings(
        app_storage_mode="azure",
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_api_key="test",
        azure_openai_chat_deployment="chat",
        azure_openai_embedding_deployment="embedding",
        azure_search_endpoint="https://example.search.windows.net",
        azure_search_api_key="test",
        azure_storage_connection_string="UseDevelopmentStorage=true",
        azure_cosmos_enabled=True,
    )

    assert settings.missing_azure_settings() == [
        "AZURE_COSMOS_ENDPOINT",
        "AZURE_COSMOS_KEY",
    ]
