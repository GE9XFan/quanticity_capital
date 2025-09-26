"""Fetch and persist the Alpha Vantage MACD endpoint."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import httpx
import structlog

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from src.core.http import HttpError, create_http_client, request_with_backoff
from src.core.redis import create_async_client, set_heartbeat, store_json
from src.core.settings import load_configuration

LOGGER = structlog.get_logger()
ENDPOINT_SLUG = "macd"


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing."""


def _resolve_endpoint(alpha_config: Mapping[str, Any]) -> Dict[str, Any]:
    endpoints = alpha_config.get("endpoints", {})
    if ENDPOINT_SLUG not in endpoints:
        raise ConfigurationError(f"Endpoint '{ENDPOINT_SLUG}' not defined in config/alpha_vantage.yml")
    return endpoints[ENDPOINT_SLUG]


def _resolve_defaults(alpha_config: Mapping[str, Any]) -> Dict[str, Any]:
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
        raise ConfigurationError("No symbols configured for macd endpoint")
    if not isinstance(symbols, Sequence):
        raise ConfigurationError("Endpoint symbols must be a sequence")
    return list(symbols)


def _merge_request_settings(defaults: Mapping[str, Any], endpoint: Mapping[str, Any]) -> Dict[str, Any]:
    request_defaults = dict(defaults.get("request", {}))
    request_overrides = endpoint.get("request", {})
    return {**request_defaults, **request_overrides}


def _build_public_params(function: str, base_params: Mapping[str, Any], symbol: str) -> Dict[str, Any]:
    params = {"function": function, **base_params, "symbol": symbol}
    return params


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


async def _process_symbol(
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
    request_params = _build_public_params(function_name, base_params, symbol)
    query_params = dict(request_params)
    query_params["apikey"] = api_key

    max_attempts = int(request_settings.get("max_attempts", 3))
    backoff_seconds = request_settings.get("backoff_seconds", [1, 3, 7])
    if isinstance(backoff_seconds, tuple):
        backoff = list(backoff_seconds)
    else:
        backoff = list(backoff_seconds)

    now = datetime.now(timezone.utc)
    heartbeat_key = f"{redis_heartbeat_prefix}:{ENDPOINT_SLUG}:{symbol}"
    redis_key = redis_key_pattern.format(symbol=symbol)

    try:
        response = await request_with_backoff(
            http_client,
            "GET",
            api_url,
            params=query_params,
            max_attempts=max_attempts,
            backoff_seconds=backoff,
        )
        response.raise_for_status()
        payload = response.json()
    except (HttpError, httpx.HTTPError, ValueError) as exc:
        LOGGER.error("ingestion.fetch_failed", endpoint=ENDPOINT_SLUG, symbol=symbol, error=str(exc))
        await set_heartbeat(
            redis_client,
            heartbeat_key,
            status="error",
            timestamp=now.isoformat(),
            extra={"error": str(exc)},
        )
        return

    if not isinstance(payload, Mapping):
        LOGGER.error(
            "ingestion.payload_invalid",
            endpoint=ENDPOINT_SLUG,
            symbol=symbol,
            reason="not-mapping",
        )
        await set_heartbeat(
            redis_client,
            heartbeat_key,
            status="error",
            timestamp=now.isoformat(),
            extra={"error": "not-mapping"},
        )
        return

    analysis_key = next((key for key in payload if key.lower().startswith("technical analysis")), None)
    analysis = payload.get(analysis_key or "") if analysis_key else None
    if not analysis or not isinstance(analysis, Mapping):
        LOGGER.error(
            "ingestion.payload_invalid",
            endpoint=ENDPOINT_SLUG,
            symbol=symbol,
            reason="missing-technical-analysis",
        )
        await set_heartbeat(
            redis_client,
            heartbeat_key,
            status="error",
            timestamp=now.isoformat(),
            extra={"error": "missing-technical-analysis"},
        )
        return

    first_key = next(iter(analysis), None)
    if not first_key or not isinstance(analysis[first_key], Mapping):
        LOGGER.error(
            "ingestion.payload_invalid",
            endpoint=ENDPOINT_SLUG,
            symbol=symbol,
            reason="malformed-macd-entry",
        )
        await set_heartbeat(
            redis_client,
            heartbeat_key,
            status="error",
            timestamp=now.isoformat(),
            extra={"error": "malformed-macd-entry"},
        )
        return

    required_keys = {"MACD", "MACD_Signal", "MACD_Hist"}
    missing_metrics = required_keys - set(analysis[first_key])
    if missing_metrics:
        LOGGER.error(
            "ingestion.payload_invalid",
            endpoint=ENDPOINT_SLUG,
            symbol=symbol,
            reason="missing-macd-components",
            missing=list(sorted(missing_metrics)),
        )
        await set_heartbeat(
            redis_client,
            heartbeat_key,
            status="error",
            timestamp=now.isoformat(),
            extra={"error": "missing-macd-components", "missing": list(sorted(missing_metrics))},
        )
        return

    storage_record = build_storage_record(
        symbol=symbol,
        endpoint_name=function_name,
        ttl_seconds=ttl_seconds,
        request_params=request_params,
        data=payload,
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
    LOGGER.info("ingestion.symbol_complete", endpoint=ENDPOINT_SLUG, symbol=symbol)


async def run(symbols: Iterable[str] | None = None) -> None:
    runtime_config, alpha_config = load_configuration()
    endpoint = _resolve_endpoint(alpha_config)
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
        redis_key_pattern = f"{key_prefix}:{ENDPOINT_SLUG}:{{symbol}}"

    heartbeat_prefix = defaults.get("redis", {}).get("heartbeat_prefix", "state:alpha_vantage")
    symbols_configured = _get_symbols(endpoint)
    request_settings = _merge_request_settings(defaults, endpoint)

    selected_symbols: List[str]
    if symbols:
        selected_symbols = [s for s in symbols if s in symbols_configured]
        missing = sorted(set(symbols) - set(selected_symbols))
        if missing:
            LOGGER.warning("ingestion.symbols.skipped", endpoint=ENDPOINT_SLUG, symbols=missing)
    else:
        selected_symbols = symbols_configured

    if not selected_symbols:
        LOGGER.warning("ingestion.no_symbols", endpoint=ENDPOINT_SLUG)
        return

    redis_client = create_async_client(runtime_config)
    timeout_seconds = float(request_settings.get("timeout_seconds", 10))

    try:
        async with create_http_client(timeout_seconds) as http_client:
            for symbol in selected_symbols:
                await _process_symbol(
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Alpha Vantage MACD data")
    parser.add_argument(
        "--symbol",
        dest="symbols",
        action="append",
        help="Limit ingestion to specific symbols (repeatable)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    asyncio.run(run(args.symbols))


if __name__ == "__main__":
    main()
