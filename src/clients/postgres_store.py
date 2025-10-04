"""Async Postgres helper for Unusual Whales REST history storage."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import asyncpg

from src.config.settings import Settings

logger = logging.getLogger(__name__)


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS uw_rest_history (
    endpoint TEXT NOT NULL,
    symbol TEXT,
    fetched_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_uw_rest_history_unique
    ON uw_rest_history (endpoint, symbol, fetched_at);
"""


class PostgresStore:
    """Async wrapper around asyncpg for history inserts."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        if self._pool is not None:
            return
        logger.debug("Connecting to Postgres at %s", self._settings.postgres_dsn)
        self._pool = await asyncpg.create_pool(self._settings.postgres_dsn, min_size=1, max_size=5)
        async with self._pool.acquire() as connection:
            await connection.execute(_CREATE_TABLE_SQL)
        logger.debug("Postgres connection ready")

    async def close(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None
        logger.debug("Postgres connection closed")

    async def write_history(self, endpoint: str, symbol: Optional[str], fetched_at_iso: str, payload: dict) -> None:
        """Insert or update a history record."""
        if self._pool is None:
            raise RuntimeError("PostgresStore.write_history called before connect()")

        fetched_at = self._parse_timestamp(fetched_at_iso)
        if fetched_at is None:
            logger.warning(
                "Skipping history write for %s (invalid timestamp: %s)",
                endpoint,
                fetched_at_iso,
            )
            return

        query = """
            INSERT INTO uw_rest_history (endpoint, symbol, fetched_at, payload)
            VALUES ($1, $2, $3, $4::jsonb)
            ON CONFLICT (endpoint, symbol, fetched_at)
            DO UPDATE SET payload = EXCLUDED.payload,
                          ingested_at = NOW();
        """
        payload_json = json.dumps(payload, separators=(",", ":"))
        async with self._pool.acquire() as connection:
            await connection.execute(query, endpoint, symbol, fetched_at, payload_json)

    @staticmethod
    def _parse_timestamp(value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            cleaned = value.strip()
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            # If there is no timezone, assume UTC
            if "+" not in cleaned and "-" not in cleaned[10:]:
                cleaned += "+00:00"
            return datetime.fromisoformat(cleaned)
        except ValueError:
            logger.error("Failed to parse timestamp: %s", value)
            return None


async def create_postgres_store(settings: Settings) -> Optional[PostgresStore]:
    if not settings.store_to_postgres:
        return None
    store = PostgresStore(settings)
    await store.connect()
    return store
