from fastapi import FastAPI

from src.api.dependencies import SettingsDep
from src.api.v1.router import api_v1_router
from src.infrastructure.config.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    is_prod = settings.app_env.lower() == "prod"
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/info", tags=["system"])
    def info(s: SettingsDep) -> dict[str, str]:
        """Non-secret config snapshot for debugging and learning."""
        return {"app_name": s.app_name, "app_env": s.app_env}

    app.include_router(api_v1_router, prefix="/api/v1")

    return app


app = create_app()
