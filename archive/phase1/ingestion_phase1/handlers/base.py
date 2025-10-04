"""Base classes for channel-specific WebSocket handlers."""

from __future__ import annotations

import abc
from typing import Any


class ChannelHandler(abc.ABC):
    """Abstract interface for WebSocket message handlers."""

    channel: str

    def __init__(self, channel: str) -> None:
        self.channel = channel

    @abc.abstractmethod
    async def handle(self, message: dict[str, Any]) -> None:
        """Process a raw message delivered for the handler's channel."""

    def subscription_payload(self) -> dict[str, Any]:
        """Return the subscription payload for this handler."""

        return {"action": "subscribe", "channel": self.channel}

    async def shutdown(self) -> None:  # pragma: no cover - default no-op
        """Allow handlers to flush buffered state during shutdown."""

        return None
