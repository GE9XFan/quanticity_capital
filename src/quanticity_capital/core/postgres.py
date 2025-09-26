"""Async Postgres engine factory."""

from __future__ import annotations

import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from ..config import AppConfig
from .settings import get_settings

_engine: Optional[AsyncEngine] = None
_engine_lock = asyncio.Lock()


async def get_postgres_engine(settings: Optional[AppConfig] = None) -> AsyncEngine:
    """Return a cached SQLAlchemy async engine configured from settings."""

    global _engine

    async with _engine_lock:
        if _engine is None:
            cfg = settings or get_settings()
            pg_cfg = cfg.runtime.postgres
            _engine = create_async_engine(
                pg_cfg.dsn,
                pool_size=pg_cfg.pool_size,
                pool_timeout=pg_cfg.timeout_seconds,
                pool_pre_ping=True,
            )
    assert _engine is not None
    return _engine


async def dispose_postgres_engine() -> None:
    """Dispose of the cached async engine."""

    global _engine
    async with _engine_lock:
        if _engine is not None:
            await _engine.dispose()
            _engine = None


__all__ = ["get_postgres_engine", "dispose_postgres_engine"]

