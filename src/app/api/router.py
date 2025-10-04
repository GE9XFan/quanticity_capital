"""API router definitions."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    """Return basic service health information."""

    return {"status": "ok"}
