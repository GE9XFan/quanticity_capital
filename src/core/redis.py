"""Redis client helpers."""
from __future__ import annotations

from redis import Redis


def create_client(url: str) -> Redis:
    """Instantiate a Redis client using the given connection URL."""

    return Redis.from_url(url, decode_responses=True)


__all__ = ["create_client"]
