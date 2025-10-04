"""WebSocket consumer for the Unusual Whales firehose."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, Iterable

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from .config import IngestionSettings
from .handlers import ChannelHandler

LOGGER = logging.getLogger(__name__)


class WebsocketConsumer:
    """Connect to Unusual Whales WebSocket streams and dispatch messages."""

    def __init__(self, settings: IngestionSettings, handlers: Iterable[ChannelHandler]) -> None:
        self._settings = settings
        self._handlers = list(handlers)
        self._handlers_by_channel: dict[str, list[ChannelHandler]] = defaultdict(list)
        for handler in self._handlers:
            self._handlers_by_channel[handler.channel].append(handler)
        token = settings.unusual_whales_api_token.get_secret_value()
        if "?" in settings.websocket_url:
            self._endpoint = f"{settings.websocket_url}&token={token}"
        else:
            self._endpoint = f"{settings.websocket_url}?token={token}"
        self._stop_event = asyncio.Event()

    async def stop(self) -> None:
        """Signal the consumer loop to shut down."""

        self._stop_event.set()

    async def run(self) -> None:
        """Run the connection loop with exponential backoff."""

        attempt = 0
        while not self._stop_event.is_set():
            try:
                await self._consume()
                attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive logging
                attempt += 1
                wait_time = min(
                    self._settings.reconnect_min_seconds * (2 ** (attempt - 1)),
                    self._settings.reconnect_max_seconds,
                )
                LOGGER.warning("WebSocket connection failed (%s). Retrying in %.1fs", exc, wait_time)
                await asyncio.sleep(wait_time)
                if attempt >= self._settings.reconnect_max_attempts:
                    LOGGER.error("Maximum reconnect attempts exceeded")
                    attempt = 0

    async def _consume(self) -> None:
        """Establish a WebSocket connection and dispatch messages."""

        LOGGER.info("Connecting to Unusual Whales WebSocket: %s", self._endpoint)
        async with connect(
            self._endpoint,
            ping_interval=self._settings.websocket_ping_interval,
            ping_timeout=self._settings.websocket_ping_timeout,
        ) as websocket:
            await self._subscribe_all(websocket)
            await self._listen(websocket)

    async def _subscribe_all(self, websocket: ClientConnection) -> None:
        """Send subscription payloads for each registered handler."""

        for handler in self._handlers:
            payload = handler.subscription_payload()
            await websocket.send(json.dumps(payload))
            LOGGER.debug("Subscribed to channel %s with payload %s", handler.channel, payload)

    async def _listen(self, websocket: ClientConnection) -> None:
        """Receive and dispatch messages until the connection closes."""

        inactivity = self._settings.inactivity_timeout_seconds
        try:
            while not self._stop_event.is_set():
                raw = await asyncio.wait_for(websocket.recv(), timeout=inactivity)
                await self._dispatch(raw)
        except asyncio.TimeoutError:
            LOGGER.warning("No WebSocket data received for %.1fs; reconnecting", inactivity)
            raise ConnectionClosed(1006, "Inactivity timeout")
        except ConnectionClosed:
            LOGGER.info("WebSocket connection closed by server")
            raise

    async def _dispatch(self, raw: str) -> None:
        """Route an incoming message to the appropriate handler(s)."""

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:  # pragma: no cover - defensive logging
            LOGGER.error("Received non-JSON payload: %s", raw)
            return

        channel = self._extract_channel(payload)
        data = self._extract_data(payload)
        if not channel or data is None:
            LOGGER.debug("Ignoring payload without channel: %s", payload)
            return

        handlers = self._handlers_by_channel.get(channel)
        if not handlers:
            LOGGER.debug("No handler registered for channel %s", channel)
            return

        for handler in handlers:
            try:
                await handler.handle(data)
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.exception("Handler %s failed to process payload: %s", handler, exc)

    @staticmethod
    def _extract_channel(payload: dict[str, Any]) -> str | None:
        """Return the channel field from a websocket message."""

        return (
            payload.get("channel")
            or payload.get("topic")
            or payload.get("stream")
        )

    @staticmethod
    def _extract_data(payload: dict[str, Any]) -> dict[str, Any] | None:
        """Return the inner data payload for a message."""

        if isinstance(payload.get("data"), dict):
            return payload["data"]
        if isinstance(payload.get("payload"), dict):
            return payload["payload"]
        # Some messages may already be flattened; treat the payload as data.
        if "channel" in payload:
            return {k: v for k, v in payload.items() if k not in {"channel", "topic", "stream"}}
        return None
