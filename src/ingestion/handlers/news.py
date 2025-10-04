"""News channel handler."""

from __future__ import annotations

import logging
from typing import Any

from ..publishers.redis import RedisPublisher
from ..persistence.postgres import PostgresRepository
from ..serializers import NewsMessage
from .base import ChannelHandler

LOGGER = logging.getLogger(__name__)


class NewsHandler(ChannelHandler):
    """Handle breaking news payloads."""

    def __init__(self, publisher: RedisPublisher, repository: PostgresRepository) -> None:
        super().__init__(channel="news")
        self._publisher = publisher
        self._repository = repository

    async def handle(self, message: dict[str, Any]) -> None:
        parsed = NewsMessage.from_raw(message)
        await self._repository.insert_news_item(parsed)
        await self._publisher.publish_news(parsed)
