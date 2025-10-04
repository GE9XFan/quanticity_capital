"""Gamma exposure channel handlers."""

from __future__ import annotations

import logging
from typing import Any

from ..publishers.redis import RedisPublisher
from ..persistence.postgres import PostgresRepository
from ..serializers import GexSnapshotMessage, GexStrikeExpiryMessage, GexStrikeMessage
from .base import ChannelHandler

LOGGER = logging.getLogger(__name__)


class GexSnapshotHandler(ChannelHandler):
    """Handle aggregated GEX websocket snapshots."""

    def __init__(self, publisher: RedisPublisher, repository: PostgresRepository) -> None:
        super().__init__(channel="gex")
        self._publisher = publisher
        self._repository = repository

    async def handle(self, message: dict[str, Any]) -> None:
        parsed = GexSnapshotMessage.from_raw(message)
        await self._repository.upsert_gex_snapshot(parsed)
        await self._publisher.publish_gex_snapshot(parsed)


class GexStrikeHandler(ChannelHandler):
    """Handle strike-level GEX channel."""

    def __init__(self, publisher: RedisPublisher, repository: PostgresRepository, tickers: list[str]) -> None:
        super().__init__(channel="gex_strike")
        self._publisher = publisher
        self._repository = repository
        self._tickers = [ticker.upper() for ticker in tickers]

    def subscription_payload(self) -> dict[str, Any]:
        payload = super().subscription_payload()
        payload["tickers"] = self._tickers
        return payload

    async def handle(self, message: dict[str, Any]) -> None:
        parsed = GexStrikeMessage.from_raw(message)
        await self._repository.upsert_gex_strike(parsed)
        await self._publisher.publish_gex_strike(parsed)


class GexStrikeExpiryHandler(ChannelHandler):
    """Handle strike+expiry GEX channel."""

    def __init__(self, publisher: RedisPublisher, repository: PostgresRepository, tickers: list[str]) -> None:
        super().__init__(channel="gex_strike_expiry")
        self._publisher = publisher
        self._repository = repository
        self._tickers = [ticker.upper() for ticker in tickers]

    def subscription_payload(self) -> dict[str, Any]:
        payload = super().subscription_payload()
        payload["tickers"] = self._tickers
        return payload

    async def handle(self, message: dict[str, Any]) -> None:
        parsed = GexStrikeExpiryMessage.from_raw(message)
        await self._repository.upsert_gex_strike_expiry(parsed)
        await self._publisher.publish_gex_strike_expiry(parsed)
