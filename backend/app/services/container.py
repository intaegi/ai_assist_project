from dataclasses import dataclass

from backend.app.core.config import Settings
from backend.app.services.ai_service import AzureAIService, LocalAIService
from backend.app.services.document_service import DocumentService
from backend.app.services.rag_service import RagService
from backend.app.services.search_service import AzureSearchService, LocalSearchService
from backend.app.services.storage import (
    AzureBlobStore,
    AzureDataStore,
    LocalBlobStore,
    LocalDataStore,
)
from scripts.seed_data import seed_store


@dataclass
class ServiceContainer:
    settings: Settings
    data_store: object
    blob_store: object
    document_service: DocumentService
    ai_service: object
    search_service: object
    rag_service: RagService


def create_services(settings: Settings) -> ServiceContainer:
    document_service = DocumentService()
    if settings.app_storage_mode == "azure":
        missing = settings.missing_azure_settings()
        if missing:
            raise RuntimeError(f"Azure設定が不足しています: {', '.join(missing)}")
        data_store = AzureDataStore(settings)
        blob_store = AzureBlobStore(settings)
        ai_service = AzureAIService(settings)
        search_service = AzureSearchService(settings, ai_service.embed)
    else:
        data_store = LocalDataStore(settings.data_dir)
        blob_store = LocalBlobStore(settings.data_dir)
        ai_service = LocalAIService()
        search_service = LocalSearchService(data_store)
        if not data_store.list_requirements():
            seed_store(data_store, settings.project_root)
    rag_service = RagService(data_store, blob_store, document_service, ai_service, search_service)
    return ServiceContainer(
        settings=settings,
        data_store=data_store,
        blob_store=blob_store,
        document_service=document_service,
        ai_service=ai_service,
        search_service=search_service,
        rag_service=rag_service,
    )
