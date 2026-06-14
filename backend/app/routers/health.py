from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "service": request.app.state.settings.app_name}


@router.get("/health/dependencies")
def dependency_health(request: Request) -> dict[str, object]:
    services = request.app.state.services
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
    checks["cosmos"] = {
        "status": "ok",
        "mode": services.settings.app_storage_mode,
    }
    return {"status": "ok" if all(item["status"] == "ok" for item in checks.values()) else "degraded", "checks": checks}
