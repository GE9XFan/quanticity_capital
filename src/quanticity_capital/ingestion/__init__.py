"""Ingestion connectors and shared helpers for vendor integrations."""

from __future__ import annotations

from .alpha_vantage import (
    ALPHA_VANTAGE_ENDPOINT_SPECS,
    DEFAULT_ALPHA_VANTAGE_CONTEXTS,
    TECHASCOPE_UNIVERSE,
    AlphaVantageClientProtocol,
    AlphaVantageConnector,
    AlphaVantageEndpointSpec,
    AlphaVantageError,
    AlphaVantageHttpClient,
    AlphaVantageInvalidRequestError,
    AlphaVantageInvalidResponseError,
    AlphaVantageRetryableError,
    AlphaVantageThrottleError,
    AlphaVantageTransportError,
)
from .rate_limits import (
    ALPHA_VANTAGE_RATE_LIMITER_SPECS,
    RateLimiterSpec,
    build_rate_limiter_map,
)

__all__ = [
    "ALPHA_VANTAGE_ENDPOINT_SPECS",
    "ALPHA_VANTAGE_RATE_LIMITER_SPECS",
    "AlphaVantageConnector",
    "AlphaVantageEndpointSpec",
    "AlphaVantageError",
    "AlphaVantageHttpClient",
    "AlphaVantageClientProtocol",
    "AlphaVantageInvalidRequestError",
    "AlphaVantageInvalidResponseError",
    "AlphaVantageRetryableError",
    "AlphaVantageThrottleError",
    "AlphaVantageTransportError",
    "RateLimiterSpec",
    "DEFAULT_ALPHA_VANTAGE_CONTEXTS",
    "TECHASCOPE_UNIVERSE",
    "build_rate_limiter_map",
]
