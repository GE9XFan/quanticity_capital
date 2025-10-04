"""Unusual Whales WebSocket consumer."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from src.clients.redis_store import RedisStore, create_store
from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

BASE_CHANNEL_MAPPING: Dict[str, str] = {
    "flow-alerts": "flow_alerts",
    "gex": "greek_exposure",
    "gex_strike": "greek_exposure_strike",
    "gex_strike_expiry": "greek_exposure_expiry",
    "news": "news",
    "price": "price_tick",
}

STREAM_PREFIX = "uw:ws"


class UWWebsocketService:
    """Connects to the Unusual Whales WebSocket API and publishes events."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.redis_store: Optional[RedisStore] = None
        self._stop_event = asyncio.Event()
        token = settings.unusual_whales_api_token
        if not token:
            raise ValueError("UNUSUAL_WHALES_API_TOKEN is required for WebSocket ingestion")
        sep = "&" if "?" in settings.unusual_whales_websocket_url else "?"
        self.endpoint = f"{settings.unusual_whales_websocket_url}{sep}token={token}"

    async def start(self) -> None:
        logger.info("Starting Unusual Whales WebSocket consumer")
        self.redis_store = await create_store(self.settings, True)
        try:
            while not self._stop_event.is_set():
                try:
                    await self._run_once()
                except ConnectionClosed as exc:
                    logger.warning("WebSocket closed (%s). Reconnecting...", exc)
                except Exception as exc:
                    logger.error("WebSocket error: %s", exc, exc_info=True)
                if not self._stop_event.is_set():
                    delay = self.settings.websocket_reconnect_seconds
                    logger.info("Reconnecting in %.1fs", delay)
                    await asyncio.sleep(delay)
        finally:
            if self.redis_store is not None:
                await self.redis_store.close()
                self.redis_store = None

    async def stop(self) -> None:
        self._stop_event.set()

    async def _run_once(self) -> None:
        assert self.redis_store is not None
        logger.info("Connecting to %s", self.endpoint)
        async with connect(self.endpoint) as websocket:
            await self._subscribe_all(websocket)
            async for raw_message in websocket:
                await self._handle_message(raw_message)

    async def _subscribe_all(self, websocket) -> None:
        for payload in self._subscription_payloads():
            await websocket.send(json.dumps(payload))
            logger.debug("Subscribed: %s", payload)

    def _subscription_payloads(self) -> Iterable[Dict[str, Any]]:
        symbols = [symbol.upper() for symbol in self.settings.symbols]
        yield {"channel": "flow-alerts", "msg_type": "join"}
        yield {"channel": "news", "msg_type": "join"}
        for symbol in symbols:
            yield {"channel": f"option_trades:{symbol}", "msg_type": "join"}
            yield {"channel": f"price:{symbol}", "msg_type": "join"}
            yield {"channel": f"gex:{symbol}", "msg_type": "join"}
            yield {"channel": f"gex_strike:{symbol}", "msg_type": "join"}
            yield {"channel": f"gex_strike_expiry:{symbol}", "msg_type": "join"}

    async def _handle_message(self, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.debug("Skipping non-JSON message: %s", raw_message)
            return

        channel, payload = self._extract_channel_payload(message)
        if not channel or payload is None:
            logger.debug("Ignoring message without channel: %s", message)
            return

        base, symbol = self._split_channel(channel)
        now_iso = datetime.now(timezone.utc).isoformat()

        stream_key = self._stream_key(base, symbol)
        event = {"received_at": now_iso, "payload": payload}
        if self.redis_store is not None:
            try:
                await self.redis_store.append_stream(stream_key, event, force=True)
            except Exception as exc:
                logger.error("Failed to append WebSocket stream %s: %s", stream_key, exc, exc_info=True)

            rest_endpoint = BASE_CHANNEL_MAPPING.get(base)
            if rest_endpoint:
                snapshot_symbol = symbol or self._extract_symbol(payload)
                try:
                    await self.redis_store.write_snapshot(
                        endpoint=rest_endpoint,
                        ticker=snapshot_symbol,
                        payload=payload,
                        fetched_at=now_iso,
                    )
                except Exception as exc:
                    logger.error("Failed to update WebSocket snapshot %s: %s", rest_endpoint, exc, exc_info=True)

    @staticmethod
    def _extract_channel_payload(message: Any) -> tuple[Optional[str], Optional[dict]]:
        if isinstance(message, list) and len(message) >= 2 and isinstance(message[0], str):
            channel = message[0]
            data = message[1]
        elif isinstance(message, dict):
            channel = (
                message.get("channel")
                or message.get("topic")
                or message.get("stream")
            )
            data = message.get("data") or message.get("payload") or message
        else:
            return None, None

        if not isinstance(channel, str):
            return None, None
        if not isinstance(data, dict):
            return channel, None
        return channel, data

    @staticmethod
    def _split_channel(channel: str) -> tuple[str, Optional[str]]:
        if ":" in channel:
            base, symbol = channel.split(":", 1)
            return base, symbol.upper()
        return channel, None

    @staticmethod
    def _extract_symbol(payload: dict) -> Optional[str]:
        for key in ("ticker", "underlying_symbol", "symbol"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value.upper()
        return None

    def _stream_key(self, base: str, symbol: Optional[str]) -> str:
        if symbol:
            return f"{STREAM_PREFIX}:{base}:{symbol}"
        return f"{STREAM_PREFIX}:{base}"


async def run_websocket_consumer() -> None:
    settings = get_settings()
    if not settings.enable_websocket:
        logger.warning("ENABLE_WEBSOCKET is false; skipping WebSocket consumer")
        return
    service = UWWebsocketService(settings)
    try:
        await service.start()
    except asyncio.CancelledError:
        logger.info("WebSocket service cancelled")
    finally:
        await service.stop()
