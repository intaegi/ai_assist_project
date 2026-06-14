from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import Settings, get_settings
from backend.app.routers import cases, health, settings
from backend.app.services.container import create_services


def create_app(app_settings: Settings | None = None) -> FastAPI:
    resolved = app_settings or get_settings()
    application = FastAPI(title="Decision RAG API", version="0.1.0")
    application.state.settings = resolved
    application.state.services = create_services(resolved)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router)
    application.include_router(settings.router)
    application.include_router(cases.router)
    return application


app = create_app()
