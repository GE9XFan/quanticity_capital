"""Redis client helpers."""

from __future__ import annotations

import json
import os
import json
from typing import Any, Dict, Mapping

import redis.asyncio as redis
import structlog

LOGGER = structlog.get_logger()


def create_async_client(runtime_config: Dict[str, Any]) -> redis.Redis:
    """Create an asyncio Redis client using runtime config and environment overrides."""
    redis_config = runtime_config.get("redis", {})
    redis_url = os.getenv("REDIS_URL", redis_config.get("url", "redis://localhost:6379/0"))
    decode_responses = redis_config.get("decode_responses", True)
    kwargs: Dict[str, Any] = {"decode_responses": decode_responses}
    if "timeout_seconds" in redis_config:
        kwargs["socket_timeout"] = redis_config["timeout_seconds"]
    LOGGER.info("redis.client.configured", url=redis_url, options=kwargs)
    return redis.Redis.from_url(redis_url, **kwargs)


async def store_json(client: redis.Redis, key: str, payload: Mapping[str, Any], ttl_seconds: int | None) -> None:
    """Serialize and store payload in Redis with optional TTL."""
    data = json.dumps(payload)
    await client.set(name=key, value=data, ex=ttl_seconds)
    LOGGER.info("redis.write", key=key, ttl=ttl_seconds, bytes=len(data))


async def set_heartbeat(
    client: redis.Redis,
    key: str,
    status: str,
    timestamp: str,
    extra: Mapping[str, Any] | None = None,
) -> None:
    """Record a lightweight heartbeat for ingestion health monitoring."""
    mapping: Dict[str, Any] = {"status": status, "timestamp": timestamp}
    if extra:
        for field, value in extra.items():
            if isinstance(value, (str, int, float)) or value is None:
                mapping[field] = "" if value is None else value
            else:
                mapping[field] = json.dumps(value)
    await client.hset(name=key, mapping=mapping)
    LOGGER.info("redis.heartbeat", key=key, status=status)


__all__ = [
    "create_async_client",
    "set_heartbeat",
    "store_json",
]
