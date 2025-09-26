"""Project entrypoint used for manual smoke checks during early development."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

import redis.asyncio as redis
import structlog
import yaml
from dotenv import load_dotenv

LOGGER = structlog.get_logger()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def load_runtime_config() -> Dict[str, Any]:
    """Load config/runtime.json if present."""
    runtime_path = CONFIG_DIR / "runtime.json"
    if not runtime_path.exists():
        return {}
    return json.loads(runtime_path.read_text())


def load_alpha_config() -> Dict[str, Any]:
    """Load config/alpha_vantage.yml if present."""
    alpha_path = CONFIG_DIR / "alpha_vantage.yml"
    if not alpha_path.exists():
        return {}
    return yaml.safe_load(alpha_path.read_text()) or {}


def load_configuration() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load environment variables first, then runtime and endpoint configs."""
    load_dotenv()
    runtime_config = load_runtime_config()
    alpha_config = load_alpha_config()
    LOGGER.info(
        "configuration.loaded",
        load_order=[".env", "config/runtime.json", "config/alpha_vantage.yml"],
        runtime_keys=list(runtime_config.keys()),
        alpha_endpoints=list(alpha_config.get("endpoints", {}).keys()),
    )
    return runtime_config, alpha_config


def build_redis_client(runtime_config: Dict[str, Any]) -> redis.Redis:
    """Construct a Redis client without establishing a connection."""
    redis_config = runtime_config.get("redis", {})
    redis_url = os.getenv("REDIS_URL", redis_config.get("url", "redis://localhost:6379/0"))
    decode_responses = redis_config.get("decode_responses", True)
    kwargs: Dict[str, Any] = {"decode_responses": decode_responses}
    if "timeout_seconds" in redis_config:
        kwargs["socket_timeout"] = redis_config["timeout_seconds"]
    LOGGER.info("redis.client.configured", url=redis_url, options=kwargs)
    return redis.Redis.from_url(redis_url, **kwargs)


async def bootstrap() -> None:
    runtime_config, _ = load_configuration()
    client = build_redis_client(runtime_config)
    try:
        LOGGER.info("bootstrap.ready", redis_client=str(client))
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(bootstrap())
