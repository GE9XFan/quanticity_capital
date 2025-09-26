"""HTTP helper routines used by ingestion modules."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

import httpx
import structlog

LOGGER = structlog.get_logger()


class HttpError(RuntimeError):
    """Raised when an HTTP request ultimately fails."""


async def request_with_backoff(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    max_attempts: int = 3,
    backoff_seconds: list[int] | tuple[int, ...] | None = None,
) -> httpx.Response:
    """Execute a request with exponential backoff between attempts."""
    attempts = 0
    errors: list[str] = []
    while attempts < max_attempts:
        attempts += 1
        try:
            response = await client.request(method, url, params=params)
            if response.status_code < 500:
                return response
            errors.append(f"{response.status_code}:{response.text[:200]}")
        except httpx.HTTPError as exc:  # network/timeout/etc
            errors.append(str(exc))
        if attempts < max_attempts and backoff_seconds:
            delay = backoff_seconds[min(attempts - 1, len(backoff_seconds) - 1)]
            LOGGER.warning(
                "http.retry",
                url=url,
                attempt=attempts,
                max_attempts=max_attempts,
                delay_seconds=delay,
                reason=errors[-1],
            )
            await asyncio.sleep(delay)
    raise HttpError(
        f"Request to {url} failed after {max_attempts} attempts: {'; '.join(errors[:5])}"
    )


def create_http_client(timeout_seconds: float = 10.0) -> httpx.AsyncClient:
    """Create an AsyncClient with sensible defaults."""
    return httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))


__all__ = ["HttpError", "create_http_client", "request_with_backoff"]
