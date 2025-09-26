from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from quanticity_capital.core.redis import (
    RetryConfig,
    dumps_json,
    ensure_ttl,
    fetch_json,
    list_index,
    loads_json,
    redis_retry,
    remove_from_index,
    write_json,
)


@pytest.mark.asyncio
async def test_redis_retry_retries_until_success() -> None:
    attempt_counter = {"count": 0}

    async def flaky_operation() -> str:
        attempt_counter["count"] += 1
        if attempt_counter["count"] < 3:
            raise RedisConnectionError("temporary failure")
        return "ok"

    result = await redis_retry(
        flaky_operation,
        retry_config=RetryConfig(attempts=5, initial_delay=0, jitter=0, max_delay=0),
    )

    assert result == "ok"
    assert attempt_counter["count"] == 3


def test_json_helpers_round_trip() -> None:
    payload = {"symbol": "SPY", "value": 1.23}
    encoded = dumps_json(payload)
    decoded = loads_json(encoded)
    assert decoded == payload
    assert loads_json(None, default={"missing": True}) == {"missing": True}


@pytest.mark.asyncio
async def test_write_json_sets_index_and_ttl() -> None:
    redis = AsyncMock()
    redis.set.return_value = True
    redis.sadd.return_value = 1
    redis.expire.return_value = True

    await write_json(
        redis,
        "raw:options:SPY",
        {"symbol": "SPY"},
        ttl=15,
        index="index:raw:options",
    )

    redis.set.assert_awaited_once()
    redis.sadd.assert_awaited_once_with("index:raw:options", "raw:options:SPY")
    redis.expire.assert_awaited_once_with("index:raw:options", 15)


@pytest.mark.asyncio
async def test_fetch_json_returns_default_when_missing() -> None:
    redis = AsyncMock()
    redis.get.return_value = None

    result = await fetch_json(redis, "unknown", default={"state": "empty"})
    assert result == {"state": "empty"}


@pytest.mark.asyncio
async def test_ensure_ttl_updates_when_below_threshold() -> None:
    redis = AsyncMock()
    redis.ttl.return_value = 5
    redis.expire.return_value = True

    await ensure_ttl(redis, "raw:options:SPY", ttl=30)
    redis.expire.assert_awaited_once_with("raw:options:SPY", 30)


@pytest.mark.asyncio
async def test_index_helpers_manage_members() -> None:
    redis = AsyncMock()
    redis.smembers.return_value = {"a", "b"}
    members = await list_index(redis, "index:test")
    assert members == {"a", "b"}

    redis.srem.return_value = 1
    await remove_from_index(redis, "index:test", ["a", "c"])
    redis.srem.assert_awaited_once_with("index:test", "a", "c")
