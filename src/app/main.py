"""FastAPI application factory."""

from fastapi import FastAPI

from .api.router import router as api_router
from .config import get_settings


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""

    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    @app.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        """Return basic application metadata."""

        return {"message": f"{settings.app_name} ready", "environment": settings.env}

    app.include_router(api_router)
    return app
