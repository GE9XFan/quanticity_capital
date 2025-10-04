"""Postgres persistence layer for Unusual Whales ingestion."""

from __future__ import annotations

import json
import logging
import hashlib
from typing import Any

import asyncpg

from ..serializers import (
    FlowAlertMessage,
    GexSnapshotMessage,
    GexStrikeExpiryMessage,
    GexStrikeMessage,
    NewsMessage,
    OptionTradeMessage,
    PriceTickMessage,
)

LOGGER = logging.getLogger(__name__)


class PostgresRepository:
    """Persist ingestion payloads into Postgres tables."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Initialise the connection pool if required."""

        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)
            LOGGER.info("Connected to Postgres for ingestion")

    async def close(self) -> None:
        """Close the connection pool."""

        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            LOGGER.info("Postgres connection pool closed")

    async def insert_flow_alert(self, message: FlowAlertMessage) -> None:
        """Persist a flow alert if it does not already exist."""

        if self._pool is None:
            raise RuntimeError("PostgresRepository.connect() must be called before use")
        payload = json.dumps(message.raw_payload)
        query = """
            INSERT INTO uw_flow_alerts (
                alert_id,
                ticker,
                event_timestamp,
                rule_name,
                direction,
                sweep,
                premium,
                aggregated_premium,
                trade_ids,
                raw_payload
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (alert_id) DO NOTHING;
        """
        trade_ids = message.trade_ids if message.trade_ids is not None else None
        async with self._pool.acquire() as connection:
            await connection.execute(
                query,
                message.alert_id,
                message.ticker.upper(),
                message.event_timestamp,
                message.rule_name,
                message.direction,
                message.sweep,
                message.premium,
                message.aggregated_premium,
                trade_ids,
                payload,
            )

    async def upsert_price_tick(self, message: PriceTickMessage) -> None:
        """Persist a price tick, updating the price if one already exists for the second."""

        if self._pool is None:
            raise RuntimeError("PostgresRepository.connect() must be called before use")
        payload = json.dumps(message.raw_payload)
        query = """
            INSERT INTO uw_price_ticks (
                ticker,
                event_timestamp,
                last_price,
                bid,
                ask,
                raw_payload
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (ticker, event_timestamp)
            DO UPDATE SET last_price = EXCLUDED.last_price,
                          bid = EXCLUDED.bid,
                          ask = EXCLUDED.ask,
                          raw_payload = EXCLUDED.raw_payload;
        """
        async with self._pool.acquire() as connection:
            await connection.execute(
                query,
                message.ticker.upper(),
                message.event_timestamp,
                message.last_price,
                message.bid,
                message.ask,
                payload,
            )

    async def bulk_insert_option_trades(self, messages: list[OptionTradeMessage]) -> None:
        """Insert a batch of option trades."""

        if not messages:
            return
        if self._pool is None:
            raise RuntimeError("PostgresRepository.connect() must be called before use")
        query = """
            INSERT INTO uw_option_trades (
                trade_id,
                ticker,
                option_symbol,
                event_timestamp,
                price,
                size,
                premium,
                side,
                exchange,
                raw_payload
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (trade_id) DO NOTHING;
        """
        rows = [
            (
                message.trade_id,
                message.ticker.upper(),
                message.option_symbol,
                message.event_timestamp,
                message.price,
                message.size,
                message.premium,
                message.side,
                message.exchange,
                json.dumps(message.raw_payload),
            )
            for message in messages
        ]
        async with self._pool.acquire() as connection:
            await connection.executemany(query, rows)

    async def upsert_gex_snapshot(self, message: GexSnapshotMessage) -> None:
        """Upsert aggregated GEX snapshot."""

        if self._pool is None:
            raise RuntimeError("PostgresRepository.connect() must be called before use")
        query = """
            INSERT INTO uw_gex_snapshot (
                ticker,
                event_timestamp,
                gamma_exposure,
                delta_exposure,
                vanna,
                charm,
                raw_payload
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (ticker, event_timestamp)
            DO UPDATE SET
                gamma_exposure = EXCLUDED.gamma_exposure,
                delta_exposure = EXCLUDED.delta_exposure,
                vanna = EXCLUDED.vanna,
                charm = EXCLUDED.charm,
                raw_payload = EXCLUDED.raw_payload;
        """
        async with self._pool.acquire() as connection:
            await connection.execute(
                query,
                message.ticker.upper(),
                message.event_timestamp,
                message.gamma_exposure,
                message.delta_exposure,
                message.vanna,
                message.charm,
                json.dumps(message.raw_payload),
            )

    async def upsert_gex_strike(self, message: GexStrikeMessage) -> None:
        """Upsert strike-level GEX snapshot."""

        if self._pool is None:
            raise RuntimeError("PostgresRepository.connect() must be called before use")
        query = """
            INSERT INTO uw_gex_strike (
                ticker,
                strike,
                event_timestamp,
                gamma_exposure,
                open_interest,
                raw_payload
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (ticker, strike, event_timestamp)
            DO UPDATE SET
                gamma_exposure = EXCLUDED.gamma_exposure,
                open_interest = EXCLUDED.open_interest,
                raw_payload = EXCLUDED.raw_payload;
        """
        async with self._pool.acquire() as connection:
            await connection.execute(
                query,
                message.ticker.upper(),
                message.strike,
                message.event_timestamp,
                message.gamma_exposure,
                message.open_interest,
                json.dumps(message.raw_payload),
            )

    async def upsert_gex_strike_expiry(self, message: GexStrikeExpiryMessage) -> None:
        """Upsert strike+expiry GEX snapshot."""

        if self._pool is None:
            raise RuntimeError("PostgresRepository.connect() must be called before use")
        query = """
            INSERT INTO uw_gex_strike_expiry (
                ticker,
                expiry,
                strike,
                event_timestamp,
                gamma_exposure,
                raw_payload
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (ticker, expiry, strike, event_timestamp)
            DO UPDATE SET
                gamma_exposure = EXCLUDED.gamma_exposure,
                raw_payload = EXCLUDED.raw_payload;
        """
        async with self._pool.acquire() as connection:
            await connection.execute(
                query,
                message.ticker.upper(),
                message.expiry,
                message.strike,
                message.event_timestamp,
                message.gamma_exposure,
                json.dumps(message.raw_payload),
            )

    async def insert_news_item(self, message: NewsMessage) -> None:
        """Insert a news headline."""

        if self._pool is None:
            raise RuntimeError("PostgresRepository.connect() must be called before use")
        query = """
            INSERT INTO uw_news (
                headline_id,
                headline,
                timestamp,
                source,
                tickers,
                is_trump_ts,
                raw_payload
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (headline_id) DO NOTHING;
        """
        async with self._pool.acquire() as connection:
            await connection.execute(
                query,
                message.headline_id,
                message.headline,
                message.timestamp,
                message.source,
                message.tickers,
                message.is_trump,
                json.dumps(message.raw_payload),
            )

    async def store_rest_payload(
        self,
        endpoint: str,
        scope: str | None,
        payload: Any,
        context: dict[str, Any],
    ) -> None:
        """Store raw REST payloads with deduplication."""

        if self._pool is None:
            raise RuntimeError("PostgresRepository.connect() must be called before use")

        document = {"response": payload, "context": context}
        payload_json = json.dumps(document, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        query = """
            INSERT INTO uw_rest_payloads (endpoint, scope, payload_hash, payload)
            VALUES ($1, $2, $3, $4::jsonb)
            ON CONFLICT (endpoint, scope, payload_hash)
            DO UPDATE SET payload = EXCLUDED.payload, fetched_at = NOW();
        """
        async with self._pool.acquire() as connection:
            await connection.execute(query, endpoint, scope, payload_hash, payload_json)
