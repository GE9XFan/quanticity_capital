"""HTTP client wrapper for Unusual Whales API.

Handles authentication, retries, and response normalization.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from urllib.parse import urljoin

import httpx
from httpx import Response

from src.config.settings import get_settings
from src.ingestion.uw_endpoints import Endpoint


logger = logging.getLogger(__name__)


class UnusualWhalesClient:
    """Async HTTP client for Unusual Whales API."""

    BASE_URL = "https://api.unusualwhales.com"

    def __init__(self, token: Optional[str] = None):
        """Initialize client with API token.

        Args:
            token: API token for authentication. If not provided, loads from settings.
        """
        self.settings = get_settings()
        self.token = token or self.settings.unusual_whales_api_token

        if not self.token:
            raise ValueError("UNUSUAL_WHALES_API_TOKEN is required")

        # Create httpx client with timeout and auth headers
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(self.settings.request_timeout_seconds),
            headers=self._build_headers(),
            follow_redirects=True,
        )

        # Track request count for rate limiting
        self.request_count = 0
        self.last_request_time = 0.0

    def _build_headers(self) -> Dict[str, str]:
        """Build common headers for all requests."""
        return {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "QuanticityCapital/1.0",
        }

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close the client."""
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def fetch_endpoint(
        self,
        endpoint: Endpoint,
        ticker: Optional[str] = None,
        retry_on_error: bool = True,
    ) -> Dict[str, Any]:
        """Fetch data from a specific endpoint.

        Args:
            endpoint: Endpoint definition
            ticker: Ticker symbol (required if endpoint.requires_ticker is True)
            retry_on_error: Whether to retry once on transient errors

        Returns:
            Dict containing the response data and metadata

        Raises:
            ValueError: If ticker is required but not provided
            httpx.HTTPStatusError: On non-recoverable HTTP errors
        """
        # Validate ticker requirement
        if endpoint.requires_ticker and not ticker:
            raise ValueError(f"Endpoint {endpoint.key} requires a ticker")

        # Build the request path
        path = endpoint.path_template
        if ticker and "{ticker}" in path:
            path = path.format(ticker=ticker)

        # Prepare request kwargs
        request_kwargs = {
            "headers": {"Accept": endpoint.accept_header},
        }

        if endpoint.query_params:
            request_kwargs["params"] = endpoint.query_params

        # Perform the request with optional retry
        max_attempts = 2 if retry_on_error else 1
        last_error = None

        for attempt in range(max_attempts):
            try:
                response = await self._make_request(path, **request_kwargs)

                # Parse response
                data = self._parse_response(response)

                # Return with metadata
                return {
                    "success": True,
                    "endpoint": endpoint.key,
                    "ticker": ticker,
                    "status_code": response.status_code,
                    "data": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Transient error on {endpoint.key} (attempt {attempt + 1}): {e}. Retrying..."
                    )
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue

            except httpx.HTTPStatusError as e:
                # Handle rate limiting specially
                if e.response.status_code == 429:
                    logger.warning(f"Rate limited on {endpoint.key}. Waiting before retry...")

                    # Try to parse retry-after header
                    retry_after = e.response.headers.get("Retry-After", "60")
                    try:
                        wait_time = float(retry_after)
                    except ValueError:
                        wait_time = 60.0

                    if attempt < max_attempts - 1:
                        await asyncio.sleep(wait_time)
                        continue

                # Server errors might be transient
                elif 500 <= e.response.status_code < 600:
                    last_error = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Server error {e.response.status_code} on {endpoint.key}. Retrying..."
                        )
                        await asyncio.sleep(5)
                        continue

                # Client errors are not retryable
                else:
                    return {
                        "success": False,
                        "endpoint": endpoint.key,
                        "ticker": ticker,
                        "status_code": e.response.status_code,
                        "error": str(e),
                        "timestamp": asyncio.get_event_loop().time(),
                    }

        # If we get here, all attempts failed
        error_msg = str(last_error) if last_error else "Unknown error"
        logger.error(f"Failed to fetch {endpoint.key} after {max_attempts} attempts: {error_msg}")

        return {
            "success": False,
            "endpoint": endpoint.key,
            "ticker": ticker,
            "error": error_msg,
            "timestamp": asyncio.get_event_loop().time(),
        }

    async def _make_request(self, path: str, **kwargs) -> Response:
        """Make an HTTP GET request with rate limiting.

        Args:
            path: API path to request
            **kwargs: Additional arguments for httpx.get()

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        # Apply rate limiting
        await self._apply_rate_limit()

        # Make the request
        response = await self.client.get(path, **kwargs)

        # Raise for status codes
        response.raise_for_status()

        # Update request tracking
        self.request_count += 1
        self.last_request_time = asyncio.get_event_loop().time()

        return response

    async def _apply_rate_limit(self):
        """Apply rate limiting to respect API limits."""
        current_time = asyncio.get_event_loop().time()

        if self.last_request_time > 0:
            elapsed = current_time - self.last_request_time
            required_delay = self.settings.rate_limit_delay

            if elapsed < required_delay:
                wait_time = required_delay - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

    def _parse_response(self, response: Response) -> Any:
        """Parse response based on content type.

        Args:
            response: httpx Response object

        Returns:
            Parsed response data (usually dict or list)

        Raises:
            ValueError: If response cannot be parsed as JSON
        """
        content_type = response.headers.get("content-type", "")

        # Most endpoints return JSON
        if "application/json" in content_type or "text/plain" in content_type:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.debug(f"Response content: {response.text[:500]}")
                raise ValueError(f"Invalid JSON response: {e}")

        # Fallback to text
        return response.text
