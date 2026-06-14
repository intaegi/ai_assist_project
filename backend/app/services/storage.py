import json
import threading
from pathlib import Path
from typing import Any

from azure.cosmos import CosmosClient, PartitionKey
from azure.storage.blob import BlobServiceClient, ContentSettings

from backend.app.core.config import Settings


class LocalDataStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = root / "database.json"
        self.lock = threading.RLock()
        if not self.path.exists():
            self._write({"cases": {}, "requirements": [], "materials": [], "past_decisions": []})

    def _read(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        with self.lock:
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)

    def save_case(self, case: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        data["cases"][case["case_id"]] = case
        self._write(data)
        return case

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        return self._read()["cases"].get(case_id)

    def list_cases(self) -> list[dict[str, Any]]:
        cases = list(self._read()["cases"].values())
        return sorted(cases, key=lambda item: item.get("updated_at", ""), reverse=True)

    def save_requirement(self, requirement: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        items = data["requirements"]
        items[:] = [
            item
            for item in items
            if not (
                item["business_category"] == requirement["business_category"]
                and item["approval_type"] == requirement["approval_type"]
            )
        ]
        items.append(requirement)
        self._write(data)
        return requirement

    def list_requirements(self) -> list[dict[str, Any]]:
        return self._read()["requirements"]

    def get_requirement(self, business_category: str, approval_type: str) -> dict[str, Any] | None:
        for item in self.list_requirements():
            if item["business_category"] == business_category and item["approval_type"] == approval_type:
                return item
        return None

    def save_material(self, material: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        data["materials"].append(material)
        self._write(data)
        return material

    def list_materials(self) -> list[dict[str, Any]]:
        return self._read()["materials"]

    def seed_past_decisions(self, decisions: list[dict[str, Any]]) -> None:
        data = self._read()
        data["past_decisions"] = decisions
        self._write(data)

    def list_past_decisions(self) -> list[dict[str, Any]]:
        return self._read()["past_decisions"]


class AzureDataStore:
    def __init__(self, settings: Settings):
        client = CosmosClient(settings.azure_cosmos_endpoint, credential=settings.azure_cosmos_key)
        database = client.get_database_client(settings.azure_cosmos_database)
        self.decisions = database.get_container_client(settings.azure_cosmos_decision_container)
        self.past = database.get_container_client(settings.azure_cosmos_past_container)

    def save_case(self, case: dict[str, Any]) -> dict[str, Any]:
        item = {**case, "partition_key": case["case_id"], "document_type": "case"}
        self.decisions.upsert_item(item)
        return case

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        try:
            item = self.decisions.read_item(item=case_id, partition_key=case_id)
            item.pop("partition_key", None)
            return item
        except Exception:
            return None

    def list_cases(self) -> list[dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.document_type = 'case' ORDER BY c.updated_at DESC"
        return list(self.decisions.query_items(query=query, enable_cross_partition_query=True))

    def save_requirement(self, requirement: dict[str, Any]) -> dict[str, Any]:
        key = f"requirement:{requirement['business_category']}:{requirement['approval_type']}"
        item = {
            **requirement,
            "id": key,
            "config_id": key,
            "partition_key": key,
            "document_type": "requirement_config",
        }
        self.decisions.upsert_item(item)
        return requirement

    def list_requirements(self) -> list[dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.document_type = 'requirement_config'"
        return list(self.decisions.query_items(query=query, enable_cross_partition_query=True))

    def get_requirement(self, business_category: str, approval_type: str) -> dict[str, Any] | None:
        key = f"requirement:{business_category}:{approval_type}"
        try:
            return self.decisions.read_item(item=key, partition_key=key)
        except Exception:
            return None

    def save_material(self, material: dict[str, Any]) -> dict[str, Any]:
        item = {
            **material,
            "partition_key": material["id"],
            "document_type": "material",
        }
        self.decisions.upsert_item(item)
        return material

    def list_materials(self) -> list[dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.document_type = 'material'"
        return list(self.decisions.query_items(query=query, enable_cross_partition_query=True))

    def seed_past_decisions(self, decisions: list[dict[str, Any]]) -> None:
        for decision in decisions:
            self.past.upsert_item(decision)

    def list_past_decisions(self) -> list[dict[str, Any]]:
        return list(self.past.read_all_items())


class LocalBlobStore:
    def __init__(self, root: Path):
        self.root = root / "files"
        self.root.mkdir(parents=True, exist_ok=True)

    def upload(self, container: str, path: str, content: bytes, content_type: str) -> str:
        destination = self.root / container / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return path.replace("\\", "/")

    def download(self, container: str, path: str) -> bytes:
        return (self.root / container / path).read_bytes()

    def delete(self, container: str, path: str) -> None:
        target = self.root / container / path
        if target.exists():
            target.unlink()

    def copy(self, container: str, source: str, destination: str, content_type: str) -> str:
        return self.upload(container, destination, self.download(container, source), content_type)

    def check(self) -> bool:
        return self.root.exists()


class AzureBlobStore:
    def __init__(self, settings: Settings):
        self.client = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)

    def upload(self, container: str, path: str, content: bytes, content_type: str) -> str:
        blob = self.client.get_blob_client(container=container, blob=path)
        blob.upload_blob(
            content,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return path

    def download(self, container: str, path: str) -> bytes:
        return self.client.get_blob_client(container=container, blob=path).download_blob().readall()

    def delete(self, container: str, path: str) -> None:
        self.client.get_blob_client(container=container, blob=path).delete_blob(delete_snapshots="include")

    def copy(self, container: str, source: str, destination: str, content_type: str) -> str:
        return self.upload(container, destination, self.download(container, source), content_type)

    def check(self) -> bool:
        next(self.client.list_containers(results_per_page=1).by_page())
        return True


def create_cosmos_structures(settings: Settings) -> None:
    client = CosmosClient(settings.azure_cosmos_endpoint, credential=settings.azure_cosmos_key)
    database = client.create_database_if_not_exists(settings.azure_cosmos_database)
    database.create_container_if_not_exists(
        id=settings.azure_cosmos_decision_container,
        partition_key=PartitionKey(path="/partition_key"),
    )
    database.create_container_if_not_exists(
        id=settings.azure_cosmos_past_container,
        partition_key=PartitionKey(path="/business_category"),
    )


def create_blob_structures(settings: Settings) -> None:
    client = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    for name in ("config-materials", "uploaded-documents", "extracted-texts", "generated-outputs"):
        client.create_container(name) if not client.get_container_client(name).exists() else None
