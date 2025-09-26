"""Project entrypoint used for manual smoke checks during early development."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict

import redis.asyncio as redis
import structlog

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.redis import create_async_client
from src.core.settings import load_configuration

LOGGER = structlog.get_logger()


def build_redis_client(runtime_config: Dict[str, Any]) -> redis.Redis:
    """Construct a Redis client without establishing a connection."""
    return create_async_client(runtime_config)


async def bootstrap() -> None:
    runtime_config, _ = load_configuration()
    client = build_redis_client(runtime_config)
    try:
        LOGGER.info("bootstrap.ready", redis_client=str(client))
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(bootstrap())
