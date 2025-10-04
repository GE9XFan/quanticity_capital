"""Redis helper for storing Unusual Whales REST snapshots."""

from __future__ import annotations

import json
import logging
from typing import Optional

from redis.asyncio import Redis

from src.config.settings import Settings

logger = logging.getLogger(__name__)


class RedisStore:
    """Minimal Redis wrapper for snapshot writes and streams."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._redis: Optional[Redis] = None
        self._store_snapshots = settings.store_to_redis
        self._enable_streams = settings.enable_history_streams and settings.redis_stream_maxlen > 0

    async def connect(self) -> None:
        if self._redis is None:
            self._redis = Redis.from_url(self._settings.redis_url, decode_responses=True)
            logger.debug("Connected to Redis at %s", self._settings.redis_url)

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()
            await self._redis.connection_pool.disconnect()
            self._redis = None
            logger.debug("Closed Redis connection")

    async def write_snapshot(self, endpoint: str, ticker: Optional[str], payload: dict, fetched_at: str) -> Optional[str]:
        """Write the latest payload into a Redis hash.

        Args:
            endpoint: Endpoint key (e.g. 'market_tide')
            ticker: Optional ticker symbol (e.g. 'SPY')
            payload: Parsed JSON payload
            fetched_at: ISO timestamp for the fetch event

        Returns:
            Redis key that was updated
        """
        if not self._store_snapshots:
            return None
        if self._redis is None:
            raise RuntimeError("RedisStore.write_snapshot called before connect()")

        key = f"uw:rest:{endpoint}" if ticker is None else f"uw:rest:{endpoint}:{ticker.upper()}"
        value = {
            "payload": json.dumps(payload, separators=(",", ":")),
            "fetched_at": fetched_at,
        }
        await self._redis.hset(key, mapping=value)
        return key

    async def append_stream(self, key: str, payload: dict, *, force: bool = False) -> Optional[str]:
        """Append an event to a capped Redis stream."""
        if not self._enable_streams and not force:
            return None
        if self._redis is None:
            raise RuntimeError("RedisStore.append_stream called before connect()")

        stream_key = key
        fields = {"payload": json.dumps(payload, separators=(",", ":"))}
        await self._redis.xadd(
            stream_key,
            fields,
            maxlen=self._settings.redis_stream_maxlen,
            approximate=True,
        )
        return stream_key


async def create_store(settings: Settings, enabled: bool) -> Optional[RedisStore]:
    if not enabled:
        return None
    store = RedisStore(settings)
    await store.connect()
    return store
