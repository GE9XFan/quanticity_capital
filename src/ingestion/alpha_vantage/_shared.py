"""Shared utilities for Alpha Vantage ingestion modules."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

import httpx
import structlog

from src.core.http import HttpError, create_http_client, request_with_backoff
from src.core.redis import create_async_client, set_heartbeat, store_json
from src.core.settings import load_configuration

LOGGER = structlog.get_logger()


class ConfigurationError(RuntimeError):
    """Raised when required Alpha Vantage configuration is missing."""


@dataclass(slots=True)
class PayloadValidationError(RuntimeError):
    """Raised when an Alpha Vantage payload fails validation."""

    message: str
    reason: str
    extra: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)
        if self.extra is None:
            self.extra = {}
        else:
            self.extra = dict(self.extra)


def _resolve_endpoint(alpha_config: Mapping[str, Any], slug: str) -> Mapping[str, Any]:
    endpoints = alpha_config.get("endpoints", {})
    if slug not in endpoints:
        raise ConfigurationError(f"Endpoint '{slug}' not defined in config/alpha_vantage.yml")
    return endpoints[slug]


def _resolve_defaults(alpha_config: Mapping[str, Any]) -> Mapping[str, Any]:
    return alpha_config.get("defaults", {})


def _get_api_key(endpoint: Mapping[str, Any], defaults: Mapping[str, Any]) -> str:
    env_name = endpoint.get("api_key_env") or defaults.get("api_key_env") or "ALPHAVANTAGE_API_KEY"
    api_key = os.getenv(env_name)
    if not api_key or api_key == "changeme":
        raise ConfigurationError(f"Alpha Vantage API key missing; set {env_name} in your environment")
    return api_key


def _get_symbols(endpoint: Mapping[str, Any]) -> List[str]:
    symbols = endpoint.get("symbols")
    if not symbols:
        raise ConfigurationError("No symbols configured for endpoint")
    if not isinstance(symbols, Sequence):
        raise ConfigurationError("Endpoint symbols must be a sequence")
    return list(symbols)


def _merge_request_settings(defaults: Mapping[str, Any], endpoint: Mapping[str, Any]) -> Dict[str, Any]:
    request_defaults = dict(defaults.get("request", {}))
    request_overrides = endpoint.get("request", {})
    return {**request_defaults, **request_overrides}



def build_storage_record(
    *,
    symbol: str,
    endpoint_name: str,
    ttl_seconds: int | None,
    request_params: Mapping[str, Any],
    data: Mapping[str, Any],
    requested_at: datetime | None = None,
) -> Dict[str, Any]:
    """Assemble the structured payload persisted to Redis."""
    as_of = (requested_at or datetime.now(timezone.utc)).isoformat()
    return {
        "symbol": symbol,
        "endpoint": endpoint_name,
        "requested_at": as_of,
        "ttl_applied": ttl_seconds,
        "request_params": dict(request_params),
        "data": data,
    }


class AlphaVantageIngestionRunner:
    """Reusable ingestion runner that encapsulates shared Alpha Vantage logic."""

    def __init__(
        self,
        *,
        slug: str,
        validator: Callable[[Mapping[str, Any], str], Mapping[str, Any]],
        retry_status_codes: Iterable[int] | None = None,
    ) -> None:
        self._slug = slug
        self._validator = validator
        self._retry_status_codes = tuple(retry_status_codes or (429,))

    async def run(self, symbols: Iterable[str] | None = None) -> None:
        runtime_config, alpha_config = load_configuration()
        endpoint = _resolve_endpoint(alpha_config, self._slug)
        defaults = _resolve_defaults(alpha_config)

        api_url = endpoint.get("api_url") or defaults.get("api_url")
        if not api_url:
            raise ConfigurationError("Alpha Vantage API URL missing from config")

        api_key = _get_api_key(endpoint, defaults)
        function_name = endpoint.get("function")
        if not function_name:
            raise ConfigurationError("Endpoint function missing from configuration")

        base_params = dict(endpoint.get("params", {}))
        cadence_seconds = endpoint.get("cadence_seconds")
        ttl_seconds = endpoint.get("redis", {}).get("ttl_seconds")
        redis_key_pattern = endpoint.get("redis", {}).get("key_pattern")
        if not redis_key_pattern:
            key_prefix = defaults.get("redis", {}).get("key_prefix", "raw:alpha_vantage")
            redis_key_pattern = f"{key_prefix}:{self._slug}:{{symbol}}"

        heartbeat_prefix = defaults.get("redis", {}).get("heartbeat_prefix", "state:alpha_vantage")
        request_settings = _merge_request_settings(defaults, endpoint)
        symbols_configured = _get_symbols(endpoint)

        selected_symbols = self._select_symbols(symbols, symbols_configured)
        if not selected_symbols:
            LOGGER.warning("ingestion.no_symbols", endpoint=self._slug)
            return

        redis_client = create_async_client(runtime_config)
        timeout_seconds = float(request_settings.get("timeout_seconds", 10))

        try:
            async with create_http_client(timeout_seconds) as http_client:
                for symbol in selected_symbols:
                    await self._process_symbol(
                        symbol,
                        api_url=api_url,
                        api_key=api_key,
                        function_name=function_name,
                        base_params=base_params,
                        request_settings=request_settings,
                        redis_key_pattern=redis_key_pattern,
                        redis_heartbeat_prefix=heartbeat_prefix,
                        ttl_seconds=ttl_seconds,
                        cadence_seconds=cadence_seconds,
                        http_client=http_client,
                        redis_client=redis_client,
                    )
        finally:
            await redis_client.aclose()

    def _select_symbols(
        self,
        supplied_symbols: Iterable[str] | None,
        configured_symbols: Sequence[str],
    ) -> List[str]:
        if not supplied_symbols:
            return list(configured_symbols)

        configured_set = set(configured_symbols)
        selected = [symbol for symbol in supplied_symbols if symbol in configured_set]
        missing = sorted(set(supplied_symbols) - set(selected))
        if missing:
            LOGGER.warning("ingestion.symbols.skipped", endpoint=self._slug, symbols=missing)
        return selected

    async def _process_symbol(
        self,
        symbol: str,
        *,
        api_url: str,
        api_key: str,
        function_name: str,
        base_params: Mapping[str, Any],
        request_settings: Mapping[str, Any],
        redis_key_pattern: str,
        redis_heartbeat_prefix: str,
        ttl_seconds: int | None,
        cadence_seconds: int | None,
        http_client: httpx.AsyncClient,
        redis_client,
    ) -> None:
        request_params: Dict[str, Any] = {"function": function_name, **base_params, "symbol": symbol}
        query_params = dict(request_params)
        query_params["apikey"] = api_key

        max_attempts = int(request_settings.get("max_attempts", 3))
        backoff_seconds = request_settings.get("backoff_seconds", [1, 3, 7])
        backoff: List[int]
        if isinstance(backoff_seconds, Sequence):
            backoff = list(backoff_seconds)
        else:
            backoff = [1, 3, 7]

        now = datetime.now(timezone.utc)
        heartbeat_key = f"{redis_heartbeat_prefix}:{self._slug}:{symbol}"
        redis_key = redis_key_pattern.format(symbol=symbol)

        try:
            response = await request_with_backoff(
                http_client,
                "GET",
                api_url,
                params=query_params,
                max_attempts=max_attempts,
                backoff_seconds=backoff,
                retry_status_codes=self._retry_status_codes,
            )
            response.raise_for_status()
            payload = response.json()
        except (HttpError, httpx.HTTPError, ValueError) as exc:
            LOGGER.error("ingestion.fetch_failed", endpoint=self._slug, symbol=symbol, error=str(exc))
            await set_heartbeat(
                redis_client,
                heartbeat_key,
                status="error",
                timestamp=now.isoformat(),
                extra={"error": str(exc)},
            )
            return

        try:
            parsed_payload = self._validate_payload(payload, symbol)
        except PayloadValidationError as exc:
            LOGGER.error(
                "ingestion.payload_invalid",
                endpoint=self._slug,
                symbol=symbol,
                reason=exc.reason,
                **(exc.extra or {}),
            )
            heartbeat_extra = {"error": exc.reason}
            if exc.extra:
                heartbeat_extra.update(exc.extra)
            await set_heartbeat(
                redis_client,
                heartbeat_key,
                status="error",
                timestamp=now.isoformat(),
                extra=heartbeat_extra,
            )
            return

        storage_record = build_storage_record(
            symbol=symbol,
            endpoint_name=function_name,
            ttl_seconds=ttl_seconds,
            request_params=request_params,
            data=parsed_payload,
            requested_at=now,
        )

        await store_json(redis_client, redis_key, storage_record, ttl_seconds)
        await set_heartbeat(
            redis_client,
            heartbeat_key,
            status="ok",
            timestamp=now.isoformat(),
            extra={
                "ttl_seconds": ttl_seconds,
                "cadence_seconds": cadence_seconds,
            },
        )
        LOGGER.info("ingestion.symbol_complete", endpoint=self._slug, symbol=symbol)

    def _validate_payload(self, payload: Any, symbol: str) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping):
            raise PayloadValidationError(
                "Alpha Vantage payload is not a mapping",
                reason="not-mapping",
                extra={},
            )

        for message_key in ("Note", "Information", "Error Message"):
            if message_key in payload:
                raise PayloadValidationError(
                    "Alpha Vantage returned an informational message instead of data",
                    reason=message_key.lower().replace(" ", "_"),
                    extra={"message": payload[message_key]},
                )

        return self._validator(payload, symbol)


__all__ = [
    "AlphaVantageIngestionRunner",
    "ConfigurationError",
    "PayloadValidationError",
    "build_storage_record",
]
