"""Service orchestration for the ingestion worker."""

from __future__ import annotations

import asyncio
import logging

from .config import IngestionSettings
from .aggregators.price_bars import PriceBarAggregator
from .handlers import (
    ChannelHandler,
    FlowAlertHandler,
    GexSnapshotHandler,
    GexStrikeExpiryHandler,
    GexStrikeHandler,
    NewsHandler,
    OptionTradeHandler,
    PriceHandler,
)
from .persistence.postgres import PostgresRepository
from .publishers.redis import RedisPublisher
from .rate_limit import TokenBucket
from .rest.client import RestClient
from .rest.scheduler import RestScheduler
from .websocket_consumer import WebsocketConsumer

LOGGER = logging.getLogger(__name__)


class IngestionService:
    """Coordinate Redis, Postgres, and WebSocket ingestion components."""

    def __init__(self, settings: IngestionSettings | None = None) -> None:
        self._settings = settings or IngestionSettings()
        self._redis_publisher = RedisPublisher(self._settings)
        self._postgres_repository = PostgresRepository(self._settings.database_url)
        self._consumer: WebsocketConsumer | None = None
        self._runner: asyncio.Task[None] | None = None
        self._price_aggregator = PriceBarAggregator()
        token_value = self._settings.unusual_whales_api_token.get_secret_value()
        headers = {"Authorization": f"Bearer {token_value}"}
        self._rest_client = RestClient(
            base_url=self._settings.rest_base_url,
            headers=headers,
            timeout=self._settings.rest_timeout_seconds,
        )
        capacity = self._settings.rate_limit_tokens_per_minute
        refill_rate = capacity / 60.0
        self._limiter = TokenBucket(capacity, refill_rate)
        self._rest_scheduler = RestScheduler(
            self._settings,
            self._rest_client,
            self._postgres_repository,
            self._limiter,
        )
        self._handlers: list[ChannelHandler] = []

    async def start(self) -> None:
        """Start the ingestion service."""

        await self._postgres_repository.connect()
        handlers: list[ChannelHandler] = [
            FlowAlertHandler(self._redis_publisher, self._postgres_repository),
            PriceHandler(
                self._redis_publisher,
                self._postgres_repository,
                self._settings.target_tickers,
                self._price_aggregator,
            ),
            OptionTradeHandler(
                self._redis_publisher,
                self._postgres_repository,
                self._settings.target_tickers,
                self._settings.option_trade_buffer_size,
                self._settings.option_trade_flush_seconds,
            ),
            GexSnapshotHandler(self._redis_publisher, self._postgres_repository),
            GexStrikeHandler(
                self._redis_publisher,
                self._postgres_repository,
                list(self._settings.target_tickers),
            ),
            GexStrikeExpiryHandler(
                self._redis_publisher,
                self._postgres_repository,
                list(self._settings.target_tickers),
            ),
            NewsHandler(self._redis_publisher, self._postgres_repository),
        ]
        self._handlers = handlers
        self._consumer = WebsocketConsumer(self._settings, handlers)
        await self._rest_scheduler.start()
        loop = asyncio.get_running_loop()
        self._runner = loop.create_task(self._consumer.run())
        LOGGER.info("Ingestion service started")

    async def stop(self) -> None:
        """Gracefully stop the ingestion service."""

        await self._rest_scheduler.stop()
        if self._consumer is not None:
            await self._consumer.stop()
        if self._runner is not None:
            self._runner.cancel()
            try:
                await self._runner
            except asyncio.CancelledError:
                pass
        for handler in self._handlers:
            await handler.shutdown()
        await self._redis_publisher.close()
        await self._postgres_repository.close()
        LOGGER.info("Ingestion service stopped")

    async def run_forever(self) -> None:
        """Run the ingestion service until cancelled."""

        await self.start()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:  # pragma: no cover - cancellation handling
            LOGGER.info("Ingestion service cancellation requested")
            raise
        finally:
            await self.stop()
