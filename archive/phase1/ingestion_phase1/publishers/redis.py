"""Redis publishing helpers for ingestion output."""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

from ..config import IngestionSettings
from ..aggregators.price_bars import PriceBar
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


class RedisPublisher:
    """Publish structured payloads to Redis streams and hashes."""

    def __init__(self, settings: IngestionSettings, client: Redis | None = None) -> None:
        self._settings = settings
        self._client = client or Redis.from_url(settings.redis_url, decode_responses=True)

    @property
    def client(self) -> Redis:
        """Return the underlying Redis client."""

        return self._client

    async def close(self) -> None:
        """Close the Redis connection."""

        await self._client.close()

    async def publish_flow_alert(self, message: FlowAlertMessage) -> None:
        """Publish a flow alert to Redis stream + snapshot hash."""

        stream_payload = message.redis_stream_payload()
        stream_key = self._settings.flow_alert_stream_key
        await self._client.xadd(
            stream_key,
            fields=stream_payload,
            maxlen=self._settings.flow_alert_stream_maxlen,
            approximate=True,
        )
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug("Published flow alert %s to stream %s", message.alert_id, stream_key)

        snapshot_key = f"{self._settings.flow_alert_snapshot_prefix}:{message.ticker.upper()}"
        snapshot_payload: dict[str, Any] = {
            "alert_id": message.alert_id,
            "event_timestamp": message.event_timestamp.isoformat(),
            "raw": json.dumps(message.raw_payload),
        }
        await self._client.hset(snapshot_key, mapping=snapshot_payload)
        await self._client.publish(snapshot_key, snapshot_payload["raw"])

    async def publish_price_tick(self, message: PriceTickMessage) -> None:
        """Publish a price tick update to Redis."""

        stream_key = f"{self._settings.price_stream_prefix}:{message.ticker.upper()}"
        await self._client.xadd(stream_key, fields=message.redis_stream_payload(), maxlen=2048, approximate=True)
        snapshot_key = f"{self._settings.price_snapshot_prefix}:{message.ticker.upper()}"
        snapshot_payload: dict[str, Any] = {
            "last_price": f"{message.last_price:.4f}",
            "event_timestamp": message.event_timestamp.isoformat(),
        }
        if message.bid is not None:
            snapshot_payload["bid"] = f"{message.bid:.4f}"
        if message.ask is not None:
            snapshot_payload["ask"] = f"{message.ask:.4f}"
        await self._client.hset(snapshot_key, mapping=snapshot_payload)
        await self._client.publish(snapshot_key, json.dumps(message.raw_payload))

    async def publish_price_bar(self, bar: PriceBar) -> None:
        """Publish a 1-minute price bar snapshot."""

        payload = {
            "start": bar.start.isoformat(),
            "end": bar.end.isoformat(),
            "open": f"{bar.open:.4f}",
            "high": f"{bar.high:.4f}",
            "low": f"{bar.low:.4f}",
            "close": f"{bar.close:.4f}",
        }
        stream_key = f"{self._settings.price_bar_stream_prefix}:{bar.ticker}"
        await self._client.xadd(stream_key, fields=payload, maxlen=720, approximate=True)
        snapshot_key = f"{self._settings.price_bar_stream_prefix}:latest:{bar.ticker}"
        await self._client.hset(snapshot_key, mapping=payload)

    async def publish_option_trade(self, message: OptionTradeMessage) -> None:
        """Publish an option trade payload."""

        stream_key = f"{self._settings.option_trade_stream_prefix}:{message.ticker.upper()}"
        await self._client.xadd(stream_key, fields=message.redis_stream_payload(), maxlen=10_000, approximate=True)

    async def publish_gex_snapshot(self, message: GexSnapshotMessage) -> None:
        """Publish aggregated GEX snapshot to Redis."""

        snapshot_key = f"{self._settings.gex_snapshot_prefix}:{message.ticker.upper()}"
        payload = {
            "event_timestamp": message.event_timestamp.isoformat(),
            "gamma_exposure": f"{message.gamma_exposure:.2f}" if message.gamma_exposure is not None else "",
            "delta_exposure": f"{message.delta_exposure:.2f}" if message.delta_exposure is not None else "",
            "vanna": f"{message.vanna:.2f}" if message.vanna is not None else "",
            "charm": f"{message.charm:.2f}" if message.charm is not None else "",
        }
        await self._client.hset(snapshot_key, mapping=payload)

    async def publish_gex_strike(self, message: GexStrikeMessage) -> None:
        """Publish GEX strike-level snapshot."""

        snapshot_key = f"{self._settings.gex_strike_snapshot_prefix}:{message.ticker.upper()}:{message.strike}"
        payload = {
            "event_timestamp": message.event_timestamp.isoformat(),
            "gamma_exposure": f"{message.gamma_exposure:.2f}" if message.gamma_exposure is not None else "",
            "open_interest": f"{message.open_interest:.2f}" if message.open_interest is not None else "",
        }
        await self._client.hset(snapshot_key, mapping=payload)

    async def publish_gex_strike_expiry(self, message: GexStrikeExpiryMessage) -> None:
        """Publish GEX strike+expiry snapshot."""

        snapshot_key = (
            f"{self._settings.gex_strike_expiry_snapshot_prefix}:"
            f"{message.ticker.upper()}:{message.expiry.date()}:{message.strike}"
        )
        payload = {
            "event_timestamp": message.event_timestamp.isoformat(),
            "gamma_exposure": f"{message.gamma_exposure:.2f}" if message.gamma_exposure is not None else "",
        }
        await self._client.hset(snapshot_key, mapping=payload)

    async def publish_news(self, message: NewsMessage) -> None:
        """Publish breaking news to Redis pub/sub and hash."""

        payload = {
            "headline_id": message.headline_id,
            "timestamp": message.timestamp.isoformat(),
            "headline": message.headline,
        }
        if message.source:
            payload["source"] = message.source
        if message.tickers:
            payload["tickers"] = ",".join(message.tickers)
        await self._client.publish(self._settings.news_pubsub_channel, json.dumps(message.raw_payload))
        snapshot_key = f"{self._settings.news_pubsub_channel}:latest"
        await self._client.hset(snapshot_key, mapping=payload)
