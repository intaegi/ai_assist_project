import os
from typing import Any

import requests


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("BACKEND_URL", "http://localhost:8000")).rstrip("/")

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        timeout = kwargs.pop("timeout", 120)
        try:
            response = requests.request(method, f"{self.base_url}{path}", timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            raise ApiError(f"バックエンドへ接続できません: {exc}") from exc
        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(str(detail))
        if response.status_code == 204:
            return None
        return response.json()

    def health(self) -> dict:
        return self._request("GET", "/health", timeout=5)

    def dependency_health(self) -> dict:
        return self._request("GET", "/health/dependencies")

    def requirements(self, category: str, approval_type: str) -> dict:
        return self._request(
            "GET",
            "/requirements",
            params={"business_category": category, "approval_type": approval_type},
        )

    def list_requirement_settings(self) -> list[dict]:
        return self._request("GET", "/settings/requirements")

    def save_requirement(self, payload: dict) -> dict:
        return self._request("POST", "/settings/requirements", json=payload)

    def upload_material(self, data: dict, file: Any) -> dict:
        files = {"file": (file.name, file.getvalue(), file.type)}
        return self._request("POST", "/settings/materials", data=data, files=files)

    def reindex(self) -> dict:
        return self._request("POST", "/settings/reindex")

    def create_case(self, data: dict, uploaded_files: list[Any]) -> dict:
        files = [
            ("files", (file.name, file.getvalue(), file.type))
            for file in uploaded_files
        ]
        return self._request("POST", "/cases", data=data, files=files)

    def generate(self, case_id: str) -> dict:
        return self._request("POST", f"/cases/{case_id}/generate")

    def list_cases(self) -> list[dict]:
        return self._request("GET", "/cases")

    def get_case(self, case_id: str) -> dict:
        return self._request("GET", f"/cases/{case_id}")

    def patch_case(self, case_id: str, payload: dict) -> dict:
        return self._request("PATCH", f"/cases/{case_id}", json=payload)

    def chat(self, case_id: str, instruction: str, target_field: str = "body") -> dict:
        return self._request(
            "POST",
            f"/cases/{case_id}/chat",
            json={"instruction": instruction, "target_field": target_field},
        )

    def clone(self, case_id: str) -> dict:
        return self._request("POST", f"/cases/{case_id}/clone")

    def add_file(self, case_id: str, file: Any) -> dict:
        files = {"file": (file.name, file.getvalue(), file.type)}
        return self._request("POST", f"/cases/{case_id}/files", files=files)

    def file_url(self, case_id: str, file_id: str) -> str:
        return f"{self.base_url}/cases/{case_id}/files/{file_id}"
