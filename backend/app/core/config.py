from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "decision-rag-api"
    app_storage_mode: Literal["local", "azure"] = "local"
    app_data_dir: Path = Path("data")
    backend_url: str = "http://localhost:8000"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = Field(default="", repr=False)
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = ""
    azure_openai_embedding_deployment: str = ""

    azure_search_endpoint: str = ""
    azure_search_api_key: str = Field(default="", repr=False)
    azure_search_index_name: str = "lim-decision-rag-index"
    azure_search_ingestion_mode: Literal["indexer", "direct"] = "indexer"
    azure_search_data_source_name: str = "lim-decision-rag-blob-datasource"
    azure_search_skillset_name: str = "lim-decision-rag-skillset"
    azure_search_indexer_name: str = "lim-decision-rag-indexer"
    azure_search_knowledge_container: str = "lim-pbl-search-knowledge"
    azure_search_indexer_interval_minutes: int = 5

    azure_storage_connection_string: str = Field(default="", repr=False)
    azure_cosmos_enabled: bool = True
    azure_cosmos_endpoint: str = ""
    azure_cosmos_key: str = Field(default="", repr=False)
    azure_cosmos_database: str = "decision-rag"
    azure_cosmos_decision_container: str = "decision-data"
    azure_cosmos_past_container: str = "past-decisions"
    azure_openai_embedding_model: Literal[
        "text-embedding-ada-002",
        "text-embedding-3-small",
        "text-embedding-3-large",
    ] = "text-embedding-3-small"

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @property
    def data_dir(self) -> Path:
        path = self.app_data_dir
        return path if path.is_absolute() else self.project_root / path

    def missing_azure_settings(self) -> list[str]:
        required = {
            "AZURE_OPENAI_ENDPOINT": self.azure_openai_endpoint,
            "AZURE_OPENAI_API_KEY": self.azure_openai_api_key,
            "AZURE_OPENAI_CHAT_DEPLOYMENT": self.azure_openai_chat_deployment,
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": self.azure_openai_embedding_deployment,
            "AZURE_SEARCH_ENDPOINT": self.azure_search_endpoint,
            "AZURE_SEARCH_API_KEY": self.azure_search_api_key,
            "AZURE_STORAGE_CONNECTION_STRING": self.azure_storage_connection_string,
        }
        if self.azure_cosmos_enabled:
            required.update(
                {
                    "AZURE_COSMOS_ENDPOINT": self.azure_cosmos_endpoint,
                    "AZURE_COSMOS_KEY": self.azure_cosmos_key,
                }
            )
        return [name for name, value in required.items() if not value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
