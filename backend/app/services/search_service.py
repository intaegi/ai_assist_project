import re
from datetime import timedelta
from typing import Any, Callable

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    AzureOpenAIEmbeddingSkill,
    HnswAlgorithmConfiguration,
    IndexingParameters,
    IndexingParametersConfiguration,
    IndexingSchedule,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchIndexer,
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    SearchIndexerSkillset,
    SearchableField,
    SimpleField,
    SplitSkill,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery

from backend.app.core.config import Settings


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[\w一-龠ぁ-んァ-ン]+", value.lower()))


class LocalSearchService:
    def __init__(self, data_store: Any):
        self.data_store = data_store

    def search(self, query: str, business_category: str, approval_type: str, top: int = 5) -> list[dict[str, Any]]:
        candidates = self.data_store.list_materials() + self.data_store.list_past_decisions()
        query_tokens = _tokens(query)
        results: list[dict[str, Any]] = []
        for item in candidates:
            category_match = item.get("business_category") in (business_category, "all", None)
            type_match = item.get("approval_type") in (approval_type, "all", None)
            if not (category_match and type_match):
                continue
            text = " ".join(str(item.get(key, "")) for key in ("title", "content", "body", "tags"))
            overlap = len(query_tokens & _tokens(text))
            score = overlap / max(len(query_tokens), 1)
            if item.get("knowledge_type") in {"policy", "required_document_rule", "template"}:
                score += 0.4
            results.append({**item, "@search.score": round(score, 4)})
        return sorted(results, key=lambda item: item["@search.score"], reverse=True)[:top]

    def index_documents(self, documents: list[dict[str, Any]]) -> int:
        # Local search reads the current data store directly. Re-saving the same
        # documents here would duplicate materials every time reindex is clicked.
        return len(documents)

    def check(self) -> bool:
        return True


class AzureSearchService:
    def __init__(
        self,
        settings: Settings,
        embed: Callable[[str], list[float]],
        blob_store: Any | None = None,
    ):
        self.settings = settings
        self.embed = embed
        self.blob_store = blob_store
        credential = AzureKeyCredential(settings.azure_search_api_key)
        self.client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=credential,
        )
        self.index_client = SearchIndexClient(settings.azure_search_endpoint, credential)
        self.indexer_client = SearchIndexerClient(settings.azure_search_endpoint, credential)

    def search(self, query: str, business_category: str, approval_type: str, top: int = 5) -> list[dict[str, Any]]:
        escaped_category = business_category.replace("'", "''")
        escaped_type = approval_type.replace("'", "''")
        filter_expression = (
            f"(business_category eq '{escaped_category}' or business_category eq 'all') and "
            f"(approval_type eq '{escaped_type}' or approval_type eq 'all')"
        )
        vector = VectorizedQuery(
            vector=self.embed(query),
            k_nearest_neighbors=top,
            fields="content_vector",
        )
        results = self.client.search(
            search_text=query,
            vector_queries=[vector],
            filter=filter_expression,
            top=top,
            select=[
                "id",
                "source_id",
                "case_id",
                "knowledge_type",
                "title",
                "content",
                "business_category",
                "approval_type",
                "approval_category_no",
                "amount",
                "required_documents",
                "source_type",
                "file_name",
                "page",
            ],
        )
        return [dict(item) for item in results]

    def index_documents(self, documents: list[dict[str, Any]]) -> int:
        if self.settings.azure_search_ingestion_mode == "indexer":
            if self.blob_store is None:
                raise RuntimeError("Indexer方式にはBlob Storageが必要です。")
            count = self.blob_store.sync_json_documents(
                self.settings.azure_search_knowledge_container,
                "documents",
                [
                    {
                        **document,
                        "source_id": document.get("source_id") or document["id"],
                    }
                    for document in documents
                ],
            )
            self.indexer_client.run_indexer(self.settings.azure_search_indexer_name)
            return count

        prepared = []
        for document in documents:
            content = str(document.get("content") or document.get("body") or "")
            prepared.append(
                {
                    **document,
                    "source_id": document.get("source_id") or document["id"],
                    "content": content,
                    "content_vector": self.embed(content),
                }
            )
        if prepared:
            self.client.upload_documents(prepared)
        return len(prepared)

    def create_index(self, vector_dimensions: int) -> None:
        fields = [
            SearchField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                searchable=True,
                filterable=True,
                analyzer_name="keyword",
            ),
            SimpleField(name="parent_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="source_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="case_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="knowledge_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="rule_priority", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
            SimpleField(name="business_category", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="approval_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchableField(name="approval_no", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="title", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="approval_category_no", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="amount", type=SearchFieldDataType.Double, filterable=True, sortable=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchField(
                name="required_documents",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True,
            ),
            SimpleField(name="source_type", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="file_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="page", type=SearchFieldDataType.Int32, filterable=True),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=vector_dimensions,
                vector_search_profile_name="decision-vector-profile",
            ),
        ]
        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="decision-hnsw")],
            profiles=[
                VectorSearchProfile(
                    name="decision-vector-profile",
                    algorithm_configuration_name="decision-hnsw",
                )
            ],
        )
        index = SearchIndex(
            name=self.settings.azure_search_index_name,
            fields=fields,
            vector_search=vector_search,
        )
        try:
            existing = self.index_client.get_index(self.settings.azure_search_index_name)
        except ResourceNotFoundError:
            existing = None
        if existing and self._index_requires_rebuild(existing, vector_dimensions):
            self.index_client.delete_index(self.settings.azure_search_index_name)
        self.index_client.create_or_update_index(index)

    @staticmethod
    def _index_requires_rebuild(index: SearchIndex, vector_dimensions: int) -> bool:
        fields = {field.name: field for field in index.fields}
        key_field = fields.get("id")
        vector_field = fields.get("content_vector")
        analyzer = getattr(getattr(key_field, "analyzer_name", None), "value", None)
        if analyzer is None:
            analyzer = getattr(key_field, "analyzer_name", None)
        return bool(
            key_field is None
            or not key_field.searchable
            or analyzer != "keyword"
            or "parent_id" not in fields
            or vector_field is None
            or vector_field.vector_search_dimensions != vector_dimensions
        )

    def create_indexer_pipeline(self, vector_dimensions: int) -> None:
        settings = self.settings
        data_source = SearchIndexerDataSourceConnection(
            name=settings.azure_search_data_source_name,
            type="azureblob",
            connection_string=settings.azure_storage_connection_string,
            container=SearchIndexerDataContainer(
                name=settings.azure_search_knowledge_container,
                query="documents",
            ),
        )
        self.indexer_client.create_or_update_data_source_connection(data_source)

        split_skill = SplitSkill(
            name="split-content",
            context="/document",
            default_language_code="ja",
            text_split_mode="pages",
            maximum_page_length=2000,
            page_overlap_length=300,
            inputs=[InputFieldMappingEntry(name="text", source="/document/content")],
            outputs=[OutputFieldMappingEntry(name="textItems", target_name="pages")],
        )
        embedding_skill = AzureOpenAIEmbeddingSkill(
            name="embed-content",
            context="/document/pages/*",
            resource_url=settings.azure_openai_endpoint,
            deployment_name=settings.azure_openai_embedding_deployment,
            model_name=settings.azure_openai_embedding_model,
            api_key=settings.azure_openai_api_key,
            dimensions=vector_dimensions,
            inputs=[InputFieldMappingEntry(name="text", source="/document/pages/*")],
            outputs=[OutputFieldMappingEntry(name="embedding", target_name="content_vector")],
        )
        mappings = [
            InputFieldMappingEntry(name="content", source="/document/pages/*"),
            InputFieldMappingEntry(
                name="content_vector",
                source="/document/pages/*/content_vector",
            ),
        ]
        for field_name in (
            "source_id",
            "case_id",
            "knowledge_type",
            "rule_priority",
            "business_category",
            "approval_type",
            "approval_no",
            "title",
            "approval_category_no",
            "amount",
            "required_documents",
            "source_type",
            "file_name",
            "page",
        ):
            mappings.append(
                InputFieldMappingEntry(
                    name=field_name,
                    source=f"/document/{field_name}",
                )
            )
        projection = SearchIndexerIndexProjection(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=settings.azure_search_index_name,
                    parent_key_field_name="parent_id",
                    source_context="/document/pages/*",
                    mappings=mappings,
                )
            ],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode="skipIndexingParentDocuments"
            ),
        )
        skillset = SearchIndexerSkillset(
            name=settings.azure_search_skillset_name,
            description="決裁RAG文書の分割とAzure OpenAI Embedding生成",
            skills=[split_skill, embedding_skill],
            index_projection=projection,
        )
        self.indexer_client.create_or_update_skillset(skillset)

        indexer = SearchIndexer(
            name=settings.azure_search_indexer_name,
            data_source_name=settings.azure_search_data_source_name,
            target_index_name=settings.azure_search_index_name,
            skillset_name=settings.azure_search_skillset_name,
            schedule=IndexingSchedule(
                interval=timedelta(minutes=settings.azure_search_indexer_interval_minutes)
            ),
            parameters=IndexingParameters(
                max_failed_items=0,
                max_failed_items_per_batch=0,
                configuration=IndexingParametersConfiguration(
                    parsing_mode="json",
                    data_to_extract="contentAndMetadata",
                    query_timeout=None,
                ),
            ),
        )
        self.indexer_client.create_or_update_indexer(indexer)

    def check(self) -> bool:
        self.index_client.get_index(self.settings.azure_search_index_name)
        if self.settings.azure_search_ingestion_mode == "indexer":
            self.indexer_client.get_data_source_connection(
                self.settings.azure_search_data_source_name
            )
            self.indexer_client.get_skillset(self.settings.azure_search_skillset_name)
            self.indexer_client.get_indexer(self.settings.azure_search_indexer_name)
        return True
