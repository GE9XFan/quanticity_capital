"""Fetch and persist top-of-book quotes from Interactive Brokers."""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence

import structlog

try:  # pragma: no cover - import guard for optional dependency
    from ib_insync import IB, Stock, Ticker  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    IB = Stock = Ticker = None  # type: ignore
    _IMPORT_ERROR = sys.exc_info()[1]
else:  # pragma: no cover - executed when dependency present
    _IMPORT_ERROR = None

from src.core.redis import create_async_client, set_heartbeat, store_json
from src.core.settings import load_ibkr_config, load_runtime_config

LOGGER = structlog.get_logger()


@dataclass(slots=True)
class QuoteConfig:
    symbols: Sequence[str]
    cadence_seconds: int
    ttl_seconds: int
    snapshot_timeout_seconds: int
    key_pattern: str
    heartbeat_pattern: str
    market_data_type: int | None = None


async def run(symbols: Iterable[str] | None = None) -> None:
    if IB is None:
        raise RuntimeError(
            "ib-insync is required for IBKR ingestion. Install the project requirements"
        ) from _IMPORT_ERROR

    runtime_config = load_runtime_config()
    ibkr_config = load_ibkr_config()

    quotes_cfg = _parse_quote_config(ibkr_config)
    target_symbols = _resolve_symbols(symbols, quotes_cfg.symbols)
    if not target_symbols:
        LOGGER.warning("ibkr.quotes.no_symbols")
        return

    redis_client = create_async_client(runtime_config)
    ib = IB()
    connection_cfg = ibkr_config.get("connection", {})
    client_id = _select_client_id(connection_cfg)

    try:
        await _connect_client(
            ib,
            host=connection_cfg.get("host", "127.0.0.1"),
            port=int(connection_cfg.get("port", 7497)),
            client_id=client_id,
            timeout=float(connection_cfg.get("connect_timeout_seconds", 10)),
            market_data_type=quotes_cfg.market_data_type,
        )

        for symbol in target_symbols:
            await _process_symbol(ib, redis_client, symbol, quotes_cfg)
            await asyncio.sleep(quotes_cfg.cadence_seconds)
    finally:
        if ib.isConnected():
            ib.disconnect()
        await redis_client.aclose()


def _parse_quote_config(config: Mapping[str, object]) -> QuoteConfig:
    quotes = config.get("quotes", {})
    redis_cfg = quotes.get("redis", {}) if isinstance(quotes, Mapping) else {}
    request_cfg = quotes.get("request", {}) if isinstance(quotes, Mapping) else {}

    symbols = list(quotes.get("symbols", [])) if isinstance(quotes, Mapping) else []
    return QuoteConfig(
        symbols=symbols,
        cadence_seconds=int(quotes.get("cadence_seconds", 3)),
        ttl_seconds=int(redis_cfg.get("ttl_seconds", 6)),
        snapshot_timeout_seconds=int(quotes.get("snapshot_timeout_seconds", 5)),
        key_pattern=str(redis_cfg.get("key_pattern", "raw:ibkr:quotes:{symbol}")),
        heartbeat_pattern=str(
            redis_cfg.get("heartbeat_pattern", "state:ibkr:quotes:{symbol}")
        ),
        market_data_type=request_cfg.get("market_data_type"),
    )


def _resolve_symbols(
    supplied_symbols: Iterable[str] | None, configured_symbols: Sequence[str]
) -> list[str]:
    if supplied_symbols is None:
        return list(configured_symbols)

    configured = set(configured_symbols)
    selected = [symbol for symbol in supplied_symbols if symbol in configured]
    missing = sorted(set(supplied_symbols) - set(selected))
    if missing:
        LOGGER.warning("ibkr.quotes.symbols_skipped", symbols=missing)
    return selected


def _select_client_id(connection_cfg: Mapping[str, object]) -> int:
    pool = connection_cfg.get("client_id_pool", [])
    if isinstance(pool, Sequence) and pool:
        return int(random.choice(pool))
    start = connection_cfg.get("client_id_start", 101)
    return int(start)


async def _connect_client(
    ib: IB,
    *,
    host: str,
    port: int,
    client_id: int,
    timeout: float,
    market_data_type: int | None,
) -> None:
    LOGGER.info("ibkr.quotes.connecting", host=host, port=port, client_id=client_id)
    connected = await ib.connectAsync(host, port, clientId=client_id, timeout=timeout)
    if not connected:
        raise RuntimeError("Unable to connect to Interactive Brokers API")
    if market_data_type is not None:
        ib.reqMarketDataType(int(market_data_type))
    LOGGER.info("ibkr.quotes.connected", client_id=client_id)


async def _process_symbol(ib: IB, redis_client, symbol: str, config: QuoteConfig) -> None:
    requested_at = datetime.now(timezone.utc)
    heartbeat_key = config.heartbeat_pattern.format(symbol=symbol)
    redis_key = config.key_pattern.format(symbol=symbol)

    contract = Stock(symbol, "SMART", "USD")

    try:
        ticker = await _request_snapshot(ib, contract, config.snapshot_timeout_seconds)
        payload = _serialize_ticker(symbol, ticker, requested_at)
        await store_json(redis_client, redis_key, payload, config.ttl_seconds)
        await set_heartbeat(
            redis_client,
            heartbeat_key,
            status="ok",
            timestamp=requested_at.isoformat(),
            extra={
                "cadence_seconds": config.cadence_seconds,
                "market_data_type": ticker.marketDataType,
            },
        )
        LOGGER.info("ibkr.quotes.symbol_complete", symbol=symbol)
    except Exception as exc:  # broad catch to ensure heartbeat logging
        LOGGER.error("ibkr.quotes.error", symbol=symbol, error=str(exc))
        await set_heartbeat(
            redis_client,
            heartbeat_key,
            status="error",
            timestamp=requested_at.isoformat(),
            extra={"error": str(exc)},
        )


async def _request_snapshot(ib: IB, contract: Stock, timeout: float) -> Ticker:
    ticker = ib.reqMktData(contract, "", snapshot=True, regulatorySnapshot=False)
    start = asyncio.get_running_loop().time()
    while True:
        if _has_quote_data(ticker):
            return ticker
        if asyncio.get_running_loop().time() - start > timeout:
            raise TimeoutError("Timed out waiting for quote snapshot")
        await ib.sleep(0.1)


def _has_quote_data(ticker: Ticker) -> bool:
    return any(
        value is not None
        for value in (
            ticker.bid,
            ticker.ask,
            ticker.last,
            ticker.close,
        )
    )


def _serialize_ticker(symbol: str, ticker: Ticker, requested_at: datetime) -> Mapping[str, object]:
    quote_ts = ticker.time or requested_at
    timestamp = quote_ts.astimezone(timezone.utc).isoformat() if isinstance(quote_ts, datetime) else requested_at.isoformat()
    return {
        "symbol": symbol,
        "source": "ibkr",
        "requested_at": requested_at.isoformat(),
        "timestamp": timestamp,
        "market_data_type": ticker.marketDataType,
        "quote": {
            "bid": _maybe_float(ticker.bid),
            "ask": _maybe_float(ticker.ask),
            "bid_size": _maybe_float(ticker.bidSize),
            "ask_size": _maybe_float(ticker.askSize),
            "last": _maybe_float(ticker.last),
            "last_size": _maybe_float(ticker.lastSize),
            "close": _maybe_float(ticker.close),
            "volume": _maybe_float(ticker.volume),
            "mark_price": _maybe_float(ticker.marketPrice),
        },
        "contract": {
            "exchange": getattr(ticker.contract, "exchange", "SMART"),
            "currency": getattr(ticker.contract, "currency", "USD"),
        },
    }


def _maybe_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch IBKR top-of-book quotes")
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


__all__ = ["run", "parse_args", "main"]


if __name__ == "__main__":
    main()
