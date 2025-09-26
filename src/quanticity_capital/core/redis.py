"""Async Redis client factory."""

from __future__ import annotations

import asyncio
from typing import Optional

from redis.asyncio import Redis, from_url

from ..config import AppConfig
from .settings import get_settings

_redis_client: Optional[Redis] = None
_redis_lock = asyncio.Lock()


async def get_redis(settings: Optional[AppConfig] = None) -> Redis:
    """Return a cached Redis client configured from settings."""

    global _redis_client

    async with _redis_lock:
        if _redis_client is None:
            cfg = settings or get_settings()
            redis_cfg = cfg.runtime.redis
            _redis_client = from_url(
                redis_cfg.url, decode_responses=redis_cfg.decode_responses
            )
    assert _redis_client is not None
    return _redis_client


async def close_redis() -> None:
    """Dispose of the cached Redis client."""

    global _redis_client
    async with _redis_lock:
        if _redis_client is not None:
            await _redis_client.close()
            _redis_client = None


__all__ = ["get_redis", "close_redis"]

