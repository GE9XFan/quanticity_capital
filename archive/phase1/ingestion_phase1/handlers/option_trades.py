"""Option trade channel handler."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Iterable

from ..publishers.redis import RedisPublisher
from ..persistence.postgres import PostgresRepository
from ..serializers import OptionTradeMessage
from .base import ChannelHandler

LOGGER = logging.getLogger(__name__)


class OptionTradeHandler(ChannelHandler):
    """Buffer and persist high-volume option trade messages."""

    def __init__(
        self,
        publisher: RedisPublisher,
        repository: PostgresRepository,
        tickers: Iterable[str],
        buffer_size: int,
        flush_interval: float,
    ) -> None:
        super().__init__(channel="option_trades")
        self._publisher = publisher
        self._repository = repository
        self._tickers = {ticker.upper() for ticker in tickers}
        self._buffer: list[OptionTradeMessage] = []
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._lock = asyncio.Lock()
        self._last_flush = time.monotonic()

    def subscription_payload(self) -> dict[str, Any]:
        """Subscribe to the trades channel limited to target tickers."""

        return {
            "action": "subscribe",
            "channel": self.channel,
            "tickers": sorted(self._tickers),
        }

    async def handle(self, message: dict[str, Any]) -> None:
        """Buffer trades and flush once thresholds are met."""

        parsed = OptionTradeMessage.from_raw(message)
        if parsed.ticker.upper() not in self._tickers:
            return
        async with self._lock:
            self._buffer.append(parsed)
            should_flush = len(self._buffer) >= self._buffer_size or (time.monotonic() - self._last_flush) >= self._flush_interval
        if should_flush:
            await self._flush()

    async def _flush(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            batch = self._buffer
            self._buffer = []
            self._last_flush = time.monotonic()
        LOGGER.debug("Flushing %d option trades", len(batch))
        await self._repository.bulk_insert_option_trades(batch)
        for message in batch:
            await self._publisher.publish_option_trade(message)

    async def shutdown(self) -> None:
        """Flush any buffered trades on shutdown."""

        await self._flush()
