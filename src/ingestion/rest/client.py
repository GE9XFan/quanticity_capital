"""Async HTTP client wrapper for Unusual Whales REST endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


class RestClient:
    """Manage a shared httpx.AsyncClient instance."""

    def __init__(self, base_url: str, headers: dict[str, str] | None = None, timeout: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "RestClient":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def start(self) -> None:
        """Initialise the underlying client if required."""

        async with self._lock:
            if self._client is None:
                self._client = httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=self._timeout)

    async def close(self) -> None:
        """Close the client."""

        async with self._lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """Perform a GET request relative to the base URL."""

        if self._client is None:
            raise RuntimeError("RestClient not started")
        return await self._client.get(path, params=params)
