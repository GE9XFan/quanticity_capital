"""Flow alert channel handler."""

from __future__ import annotations

import logging
from typing import Any

from ..publishers.redis import RedisPublisher
from ..persistence.postgres import PostgresRepository
from ..serializers import FlowAlertMessage
from .base import ChannelHandler

LOGGER = logging.getLogger(__name__)


class FlowAlertHandler(ChannelHandler):
    """Handle flow alert websocket payloads."""

    def __init__(self, publisher: RedisPublisher, repository: PostgresRepository) -> None:
        super().__init__(channel="flow-alerts")
        self._publisher = publisher
        self._repository = repository

    async def handle(self, message: dict[str, Any]) -> None:
        """Parse the payload and push to Redis/Postgres."""

        try:
            parsed = FlowAlertMessage.from_raw(message)
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception("Failed to parse flow alert payload: %s", exc)
            return

        LOGGER.debug("Processing flow alert %s for %s", parsed.alert_id, parsed.ticker)
        await self._repository.insert_flow_alert(parsed)
        await self._publisher.publish_flow_alert(parsed)
