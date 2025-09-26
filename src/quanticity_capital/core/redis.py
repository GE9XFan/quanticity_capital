"""Async Redis client factory and helper utilities."""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Optional, Protocol, TypeVar, cast

try:  # pragma: no cover - executed when orjson is installed
    import orjson as _orjson
except ImportError:  # pragma: no cover - exercised when dependency unavailable
    _orjson = None
from redis.asyncio import Redis, from_url
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from ..config import AppConfig
from .settings import get_settings

T = TypeVar("T")

_redis_client: Optional[Redis] = None
_redis_lock = asyncio.Lock()


class SupportsWarning(Protocol):
    """Minimal logger interface for retry warnings."""

    def warning(
        self,
        event: str | None = ...,
        *args: Any,
        **kwargs: Any,
    ) -> Any: ...


@dataclass(slots=True)
class RetryConfig:
    """Configuration for retrying Redis commands."""

    attempts: int = 5
    initial_delay: float = 0.2
    max_delay: float = 2.0
    jitter: float = 0.1
    exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (
            RedisConnectionError,
            RedisTimeoutError,
            ConnectionError,
            TimeoutError,
        )
    )


async def get_redis(settings: Optional[AppConfig] = None) -> Redis:
    """Return a cached Redis client configured from settings."""

    global _redis_client

    async with _redis_lock:
        if _redis_client is None:
            cfg = settings or get_settings()
            redis_cfg = cfg.runtime.redis
            _redis_client = from_url(redis_cfg.url, decode_responses=redis_cfg.decode_responses)
    assert _redis_client is not None
    return _redis_client


async def close_redis() -> None:
    """Dispose of the cached Redis client."""

    global _redis_client
    async with _redis_lock:
        if _redis_client is not None:
            await _redis_client.close()
            _redis_client = None


async def redis_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    retry_config: Optional[RetryConfig] = None,
    logger: Optional[SupportsWarning] = None,
) -> T:
    """Execute ``operation`` with exponential backoff."""

    cfg = retry_config or RetryConfig()
    delay = cfg.initial_delay

    for attempt in range(1, cfg.attempts + 1):
        try:
            return await operation()
        except cfg.exceptions as exc:  # type: ignore[misc]
            if attempt >= cfg.attempts:
                raise
            sleep_for = min(delay, cfg.max_delay)
            if cfg.jitter:
                sleep_for += random.uniform(0, cfg.jitter)
            if logger is not None:
                logger.warning(
                    "Redis operation failed; retrying",
                    extra={"attempt": attempt, "sleep_for": sleep_for},
                    exc_info=exc,
                )
            await asyncio.sleep(max(sleep_for, 0))
            delay = min(delay * 2, cfg.max_delay)
    raise RuntimeError("redis_retry exhausted without returning")


def dumps_json(value: Any) -> str:
    """Serialize ``value`` returning a UTF-8 ``str``."""

    if _orjson is not None:
        encoded = _orjson.dumps(value)
        return encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def loads_json(value: Optional[bytes | str], default: Any = None) -> Any:
    """Deserialize ``value`` produced by :func:`dumps_json`."""

    if value is None:
        return default
    if _orjson is not None:
        if isinstance(value, bytes):
            return _orjson.loads(value)
        return _orjson.loads(value.encode("utf-8"))
    if isinstance(value, bytes):
        return json.loads(value.decode("utf-8"))
    return json.loads(value)


async def write_json(
    redis: Redis,
    key: str,
    payload: Any,
    *,
    ttl: Optional[int] = None,
    index: Optional[str] = None,
    index_member: Optional[str] = None,
    retry_config: Optional[RetryConfig] = None,
    logger: Optional[SupportsWarning] = None,
) -> None:
    """Store ``payload`` at ``key`` with optional TTL and index bookkeeping."""

    value = dumps_json(payload)

    async def _set() -> bool:
        if ttl is not None:
            return await redis.set(key, value, ex=ttl)
        return await redis.set(key, value)

    await redis_retry(_set, retry_config=retry_config, logger=logger)

    if index is not None:
        member = index_member or key

        async def _add_index() -> int:
            return await cast(Awaitable[int], redis.sadd(index, member))

        await redis_retry(_add_index, retry_config=retry_config, logger=logger)
        if ttl is not None:

            async def _expire_index() -> bool:
                return await cast(Awaitable[bool], redis.expire(index, ttl))

            await redis_retry(
                _expire_index,
                retry_config=retry_config,
                logger=logger,
            )


async def fetch_json(
    redis: Redis,
    key: str,
    *,
    default: Any = None,
    retry_config: Optional[RetryConfig] = None,
    logger: Optional[SupportsWarning] = None,
) -> Any:
    """Retrieve JSON payload stored by :func:`write_json`."""

    async def _get() -> Optional[bytes | str]:
        return await cast(Awaitable[Optional[bytes | str]], redis.get(key))

    value = await redis_retry(_get, retry_config=retry_config, logger=logger)
    if value is None:
        return default
    return loads_json(value, default)


async def ensure_ttl(
    redis: Redis,
    key: str,
    ttl: int,
    *,
    retry_config: Optional[RetryConfig] = None,
    logger: Optional[SupportsWarning] = None,
) -> None:
    """Extend TTL for ``key`` when it is missing or lower than ``ttl`` seconds."""

    async def _ttl() -> int | None:
        return await cast(Awaitable[int | None], redis.ttl(key))

    current_ttl = await redis_retry(_ttl, retry_config=retry_config, logger=logger)
    if current_ttl is None or current_ttl < 0 or current_ttl < ttl:

        async def _expire_key() -> bool:
            return await cast(Awaitable[bool], redis.expire(key, ttl))

        await redis_retry(
            _expire_key,
            retry_config=retry_config,
            logger=logger,
        )


async def remove_from_index(
    redis: Redis,
    index_key: str,
    members: Iterable[str],
    *,
    retry_config: Optional[RetryConfig] = None,
    logger: Optional[SupportsWarning] = None,
) -> None:
    """Remove ``members`` from an index set."""

    member_list = list(members)
    if not member_list:
        return

    async def _srem() -> int:
        return await cast(Awaitable[int], redis.srem(index_key, *member_list))

    await redis_retry(
        _srem,
        retry_config=retry_config,
        logger=logger,
    )


async def list_index(
    redis: Redis,
    index_key: str,
    *,
    retry_config: Optional[RetryConfig] = None,
    logger: Optional[SupportsWarning] = None,
) -> set[str]:
    """Return members of an index set."""

    async def _members() -> set[bytes | str]:
        return await cast(Awaitable[set[bytes | str]], redis.smembers(index_key))

    members = await redis_retry(
        _members,
        retry_config=retry_config,
        logger=logger,
    )
    return {str(member) for member in members}


__all__ = [
    "RetryConfig",
    "close_redis",
    "dumps_json",
    "ensure_ttl",
    "fetch_json",
    "get_redis",
    "list_index",
    "loads_json",
    "redis_retry",
    "remove_from_index",
    "write_json",
]
