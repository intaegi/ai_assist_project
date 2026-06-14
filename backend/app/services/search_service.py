import re
from typing import Any, Callable

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SimpleField,
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
        for document in documents:
            if document.get("knowledge_type") == "past_case":
                continue
            self.data_store.save_material(document)
        return len(documents)

    def check(self) -> bool:
        return True


class AzureSearchService:
    def __init__(self, settings: Settings, embed: Callable[[str], list[float]]):
        self.settings = settings
        self.embed = embed
        credential = AzureKeyCredential(settings.azure_search_api_key)
        self.client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=credential,
        )
        self.index_client = SearchIndexClient(settings.azure_search_endpoint, credential)

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
        prepared = []
        for document in documents:
            content = str(document.get("content") or document.get("body") or "")
            prepared.append({**document, "content": content, "content_vector": self.embed(content)})
        if prepared:
            self.client.upload_documents(prepared)
        return len(prepared)

    def create_index(self, vector_dimensions: int) -> None:
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
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
        self.index_client.create_or_update_index(index)

    def check(self) -> bool:
        self.index_client.get_index(self.settings.azure_search_index_name)
        return True
