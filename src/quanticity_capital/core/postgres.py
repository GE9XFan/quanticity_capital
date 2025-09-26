"""Async Postgres engine factory and session helpers."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import AppConfig
from .settings import get_settings

_engine: Optional[AsyncEngine] = None
_engine_lock = asyncio.Lock()
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_session_lock = asyncio.Lock()


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


async def get_sessionmaker(
    settings: Optional[AppConfig] = None,
) -> async_sessionmaker[AsyncSession]:
    """Return a cached ``async_sessionmaker`` bound to the shared engine."""

    global _session_factory

    async with _session_lock:
        if _session_factory is None:
            engine = await get_postgres_engine(settings)
            _session_factory = async_sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
    assert _session_factory is not None
    return _session_factory


@asynccontextmanager
async def session_scope(
    settings: Optional[AppConfig] = None,
) -> AsyncIterator[AsyncSession]:
    """Async context manager yielding a session tied to the shared engine."""

    session_maker = await get_sessionmaker(settings)
    async with session_maker() as session:
        yield session


async def dispose_postgres_engine() -> None:
    """Dispose of the cached async engine and session factory."""

    global _engine
    global _session_factory

    async with _engine_lock:
        if _engine is not None:
            await _engine.dispose()
            _engine = None

    async with _session_lock:
        _session_factory = None


__all__ = [
    "dispose_postgres_engine",
    "get_postgres_engine",
    "get_sessionmaker",
    "session_scope",
]
