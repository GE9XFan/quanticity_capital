"""Price ticker channel handler."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from ..aggregators.price_bars import PriceBarAggregator
from ..publishers.redis import RedisPublisher
from ..persistence.postgres import PostgresRepository
from ..serializers import PriceTickMessage
from .base import ChannelHandler

LOGGER = logging.getLogger(__name__)


class PriceHandler(ChannelHandler):
    """Handle price ticker updates for the configured ticker universe."""

    def __init__(
        self,
        publisher: RedisPublisher,
        repository: PostgresRepository,
        tickers: Iterable[str],
        aggregator: PriceBarAggregator,
    ) -> None:
        super().__init__(channel="price")
        self._publisher = publisher
        self._repository = repository
        self._tickers = {ticker.upper() for ticker in tickers}
        self._aggregator = aggregator

    def subscription_payload(self) -> dict[str, Any]:
        """Override subscription payload to include ticker filter."""

        return {
            "action": "subscribe",
            "channel": self.channel,
            "tickers": sorted(self._tickers),
        }

    async def handle(self, message: dict[str, Any]) -> None:
        """Persist the price tick if it relates to the target ticker set."""

        if "ticker" not in message:
            # Some payloads omit the ticker; infer from handler context when possible.
            if len(self._tickers) == 1:
                message["ticker"] = next(iter(self._tickers))
            else:
                # fall back to symbol if present; handler subscription includes target tickers
                message["ticker"] = message.get("symbol") or message.get("underlying_symbol") or next(iter(self._tickers))
        parsed = PriceTickMessage.from_raw(message)
        if parsed.ticker.upper() not in self._tickers:
            LOGGER.debug("Ignoring price tick for %s", parsed.ticker)
            return
        await self._repository.upsert_price_tick(parsed)
        await self._publisher.publish_price_tick(parsed)
        completed, current = self._aggregator.add_tick(parsed)
        if completed is not None:
            await self._publisher.publish_price_bar(completed)
        if current is not None:
            await self._publisher.publish_price_bar(current)
