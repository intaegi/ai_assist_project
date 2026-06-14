from fastapi import APIRouter, Request

from backend.app.services.storage import REQUIRED_BLOB_CONTAINERS

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "service": request.app.state.settings.app_name}


@router.get("/health/dependencies")
def dependency_health(request: Request) -> dict[str, object]:
    services = request.app.state.services
    mode = services.settings.app_storage_mode
    checks = {}
    for name, service in (
        ("blob", services.blob_store),
        ("search", services.search_service),
        ("openai", services.ai_service),
    ):
        try:
            checks[name] = {"status": "ok" if service.check() else "error"}
        except Exception as exc:
            checks[name] = {"status": "error", "message": str(exc)}
    if services.data_store_mode == "azure":
        try:
            checks["cosmos"] = {
                "status": "ok" if services.data_store.check() else "error",
                "mode": "azure",
            }
        except Exception as exc:
            checks["cosmos"] = {"status": "error", "mode": "azure", "message": str(exc)}
    else:
        checks["cosmos"] = {
            "status": "skipped",
            "mode": "local",
            "message": (
                "Cosmos DBは無効です。決裁設定と履歴はローカルdata/database.jsonへ保存します。"
                if mode == "azure"
                else "Local modeでは使用しません。"
            ),
        }
    if mode == "azure":
        checks["blob"]["details"] = {
            "storage_account": getattr(services.blob_store.client, "account_name", ""),
            "containers": list(REQUIRED_BLOB_CONTAINERS),
        }
        checks["search"]["details"] = {
            "index": services.settings.azure_search_index_name,
            "registration_method": "application_direct_push",
            "indexer_required": False,
            "data_source_required": False,
            "skillset_required": False,
        }
        checks["cosmos"]["details"] = {
            "database": (
                services.settings.azure_cosmos_database
                if services.data_store_mode == "azure"
                else "data/database.json"
            )
        }
    has_error = any(item["status"] == "error" for item in checks.values())
    return {
        "status": "degraded" if has_error else "ok",
        "mode": mode,
        "data_store_mode": services.data_store_mode,
        "checks": checks,
    }
