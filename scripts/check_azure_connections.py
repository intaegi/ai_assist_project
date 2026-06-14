import argparse
import sys

from dotenv import dotenv_values

from backend.app.core.config import Settings
from backend.app.services.ai_service import AzureAIService
from backend.app.services.search_service import AzureSearchService
from backend.app.services.storage import (
    REQUIRED_BLOB_CONTAINERS,
    AzureBlobStore,
    AzureDataStore,
)


def print_result(name: str, status: str, message: str) -> None:
    print(f"[{status}] {name}: {message}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Azureへ接続せず、環境変数名と必須値だけを確認します。",
    )
    args = parser.parse_args()

    raw = dotenv_values(".env")
    if raw.get("AZURE_SEARCH_ENDPOIN") and not raw.get("AZURE_SEARCH_ENDPOINT"):
        print_result(
            "設定",
            "ERROR",
            "AZURE_SEARCH_ENDPOINは誤記です。AZURE_SEARCH_ENDPOINTへ修正してください。",
        )

    settings = Settings()
    missing = settings.missing_azure_settings()
    if missing:
        print_result("設定", "ERROR", f"未設定: {', '.join(missing)}")
    else:
        print_result("設定", "OK", "Azure接続に必要な環境変数が設定されています。")

    if args.config_only:
        print_result("接続テスト", "SKIP", "--config-onlyのためAzure APIは呼び出していません。")
        return

    if (
        settings.azure_openai_endpoint
        and settings.azure_openai_api_key
        and settings.azure_openai_embedding_deployment
    ):
        try:
            ai_service = AzureAIService(settings)
            dimensions = len(ai_service.embed("接続確認"))
            print_result("Azure OpenAI Embedding", "OK", f"接続済み、dimensions={dimensions}")
            try:
                ai_service.client.chat.completions.create(
                    model=settings.azure_openai_chat_deployment,
                    messages=[{"role": "user", "content": "接続確認。OKのみ回答してください。"}],
                    max_tokens=3,
                    temperature=0,
                )
                print_result("Azure OpenAI Chat", "OK", "接続済み")
            except Exception as exc:
                print_result("Azure OpenAI Chat", "ERROR", str(exc))
        except Exception as exc:
            ai_service = None
            print_result("Azure OpenAI Embedding", "ERROR", str(exc))
    else:
        ai_service = None
        print_result("Azure OpenAI", "SKIP", "Endpoint、Key、Deploymentを設定してください。")

    blob = None
    if settings.azure_storage_connection_string:
        try:
            blob = AzureBlobStore(settings)
            existing = {item["name"] for item in blob.client.list_containers()}
            required_containers = set(REQUIRED_BLOB_CONTAINERS)
            required_containers.add(settings.azure_search_knowledge_container)
            missing_containers = sorted(required_containers - existing)
            print_result(
                "Azure Blob Storage",
                "OK" if not missing_containers else "ERROR",
                (
                    f"account={blob.client.account_name}, "
                    f"containers={', '.join(sorted(required_containers))}"
                    if not missing_containers
                    else f"不足コンテナ: {', '.join(missing_containers)}"
                ),
            )
        except Exception as exc:
            print_result("Azure Blob Storage", "ERROR", str(exc))
    else:
        print_result("Azure Blob Storage", "SKIP", "接続文字列を設定してください。")

    if settings.azure_search_endpoint and settings.azure_search_api_key:
        try:
            embed = ai_service.embed if ai_service else lambda _: []
            search = AzureSearchService(settings, embed, blob)
            indexer_status = ""
            data_source_status = ""
            if settings.azure_search_ingestion_mode == "indexer":
                status = search.indexer_client.get_indexer_status(
                    settings.azure_search_indexer_name
                )
                last_status = getattr(status.last_result, "status", "not-run")
                indexer_status = f", indexer_status={last_status}"
                data_source = search.indexer_client.get_data_source_connection(
                    settings.azure_search_data_source_name
                )
                data_source_status = (
                    f", data_source={data_source.name}"
                    f"->{data_source.container.name}/{data_source.container.query or ''}"
                )
            print_result(
                "Azure AI Search",
                "OK" if search.check() else "ERROR",
                (
                    f"index={settings.azure_search_index_name}, "
                    f"documents={search.client.get_document_count()}, "
                    f"registration={settings.azure_search_ingestion_mode}"
                    f"{indexer_status}{data_source_status}"
                ),
            )
        except Exception as exc:
            print_result("Azure AI Search", "ERROR", str(exc))
    else:
        print_result("Azure AI Search", "SKIP", "EndpointとAPI Keyを設定してください。")

    if settings.azure_cosmos_enabled:
        if settings.azure_cosmos_endpoint and settings.azure_cosmos_key:
            try:
                print_result(
                    "Azure Cosmos DB",
                    "OK" if AzureDataStore(settings).check() else "ERROR",
                    f"database={settings.azure_cosmos_database}",
                )
            except Exception as exc:
                print_result("Azure Cosmos DB", "ERROR", str(exc))
        else:
            print_result("Azure Cosmos DB", "ERROR", "EndpointとKeyを設定してください。")
    else:
        print_result(
            "Azure Cosmos DB",
            "SKIP",
            "AZURE_COSMOS_ENABLED=false。履歴はローカルdata/database.jsonへ保存します。",
        )


if __name__ == "__main__":
    main()
