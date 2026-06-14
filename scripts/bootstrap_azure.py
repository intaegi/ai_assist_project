import sys

from backend.app.core.config import Settings
from backend.app.services.ai_service import AzureAIService
from backend.app.services.search_service import AzureSearchService
from backend.app.services.storage import (
    AzureBlobStore,
    AzureDataStore,
    LocalDataStore,
    create_blob_structures,
    create_cosmos_structures,
)
from scripts.seed_data import load_seed_data, seed_store


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    settings = Settings(app_storage_mode="azure")
    missing = settings.missing_azure_settings()
    if missing:
        raise SystemExit(f"Azure設定が不足しています: {', '.join(missing)}")

    print("1/5 Blob Storageコンテナを確認します")
    create_blob_structures(settings)
    blob_store = AzureBlobStore(settings)

    if settings.azure_cosmos_enabled:
        print("2/5 Cosmos DBデータベースとコンテナを確認します")
        create_cosmos_structures(settings)
        data_store = AzureDataStore(settings)
    else:
        print("2/5 Cosmos DBは無効です。ローカル履歴ストアを使用します")
        data_store = LocalDataStore(settings.data_dir)

    print("3/5 Azure OpenAI Embedding接続を確認します")
    ai_service = AzureAIService(settings)
    dimensions = len(ai_service.embed("決裁RAGインデックス初期化"))

    print(f"4/5 AI Searchインデックスを作成します（vector dimensions={dimensions}）")
    search_service = AzureSearchService(settings, ai_service.embed, blob_store)
    search_service.create_index(dimensions)
    if settings.azure_search_ingestion_mode == "indexer":
        search_service.create_indexer_pipeline(dimensions)

    print("5/5 架空サンプルデータを登録します")
    counts = seed_store(data_store, settings.project_root)
    _, decisions, materials = load_seed_data(settings.project_root)
    for material in materials:
        blob_store.upload(
            "config-materials",
            material["storage_path"],
            material["content"].encode("utf-8"),
            "text/markdown",
        )
    documents = []
    for item in materials + decisions:
        documents.append(
            {
                "id": item["id"],
                "case_id": item.get("case_id", ""),
                "knowledge_type": item.get("knowledge_type", "past_case"),
                "rule_priority": int(item.get("rule_priority", 2)),
                "business_category": item.get("business_category", "all"),
                "approval_type": item.get("approval_type", "all"),
                "approval_no": item.get("approval_no", ""),
                "title": item.get("title", ""),
                "approval_category_no": item.get("approval_category_no", ""),
                "amount": item.get("amount"),
                "content": item.get("content") or item.get("body", ""),
                "required_documents": item.get("required_documents", []),
                "source_type": item.get("source_type", item.get("knowledge_type", "reference")),
                "file_name": item.get("file_name", ""),
                "page": item.get("page"),
            }
        )
    indexed = search_service.index_documents(documents)
    print(
        "完了: "
        f"{counts}, indexed={indexed}, index={settings.azure_search_index_name}, "
        f"ingestion={settings.azure_search_ingestion_mode}"
    )


if __name__ == "__main__":
    main()
