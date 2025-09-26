"""Rotate Interactive Brokers level-2 market depth subscriptions."""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import structlog

try:  # pragma: no cover - optional dependency guard
    from ib_insync import IB, Stock, Ticker  # type: ignore
except ImportError:  # pragma: no cover
    IB = Stock = Ticker = None  # type: ignore
    _IMPORT_ERROR = sys.exc_info()[1]
else:  # pragma: no cover
    _IMPORT_ERROR = None

from src.core.redis import create_async_client, set_heartbeat, store_json
from src.core.settings import load_ibkr_config, load_runtime_config

LOGGER = structlog.get_logger()


@dataclass(slots=True)
class Level2Config:
    rotation_groups: List[Tuple[str, List[str]]]
    depth_levels: int
    cadence_seconds: int
    max_concurrent_symbols: int
    key_pattern: str
    heartbeat_pattern: str
    ttl_seconds: int
    market_depth_type: str | None = None
    contract_overrides: Dict[str, Mapping[str, str]] | None = None


async def run(groups: Iterable[str] | None = None) -> None:
    if IB is None:
        raise RuntimeError(
            "ib-insync is required for IBKR level-2 ingestion. Install project requirements."
        ) from _IMPORT_ERROR

    runtime_config = load_runtime_config()
    ibkr_config = load_ibkr_config()
    level2_config = _parse_level2_config(ibkr_config)
    rotation = _resolve_rotation(level2_config.rotation_groups, groups)
    if not rotation:
        LOGGER.warning("ibkr.level2.no_groups")
        return

    redis_client = create_async_client(runtime_config)
    ib = IB()
    connection_cfg = ibkr_config.get("connection", {})
    client_id = _select_client_id(connection_cfg)

    try:
        await _connect(
            ib,
            host=connection_cfg.get("host", "127.0.0.1"),
            port=int(connection_cfg.get("port", 7497)),
            client_id=client_id,
            timeout=float(connection_cfg.get("connect_timeout_seconds", 10)),
            market_depth_type=level2_config.market_depth_type,
        )

        for group_name, symbols in rotation:
            await _process_group(
                ib,
                redis_client,
                group_name,
                symbols,
                level2_config,
            )
    finally:
        if ib.isConnected():
            ib.disconnect()
        await redis_client.aclose()


def _parse_level2_config(config: Mapping[str, object]) -> Level2Config:
    section = config.get("level2_depth", {})
    if not isinstance(section, Mapping):
        raise ValueError("level2_depth section missing in config/ibkr.yml")

    groups_cfg = section.get("rotation_groups", {})
    if not isinstance(groups_cfg, Mapping) or not groups_cfg:
        raise ValueError("rotation_groups must be defined for level2_depth")

    rotation: List[Tuple[str, List[str]]] = []
    for name, symbols in groups_cfg.items():
        if not isinstance(symbols, Sequence) or not symbols:
            raise ValueError(f"Rotation group {name!r} must list symbols")
        rotation.append((str(name), [str(sym) for sym in symbols]))

    redis_cfg = section.get("redis", {}) if isinstance(section, Mapping) else {}
    request_cfg = section.get("request", {}) if isinstance(section, Mapping) else {}

    return Level2Config(
        rotation_groups=rotation,
        depth_levels=int(section.get("depth_levels", 10)),
        cadence_seconds=int(section.get("cadence_seconds", 5)),
        max_concurrent_symbols=int(section.get("max_concurrent_symbols", 3)),
        key_pattern=str(redis_cfg.get("key_pattern", "raw:ibkr:l2:{symbol}")),
        heartbeat_pattern=str(
            redis_cfg.get("heartbeat_pattern", "state:ibkr:l2:{symbol}")
        ),
        ttl_seconds=int(redis_cfg.get("ttl_seconds", 10)),
        market_depth_type=request_cfg.get("market_depth_type"),
        contract_overrides={
            str(symbol): dict(override)
            for symbol, override in (section.get("contract_overrides", {}) or {}).items()
            if isinstance(override, Mapping)
        },
    )


def _resolve_rotation(
    rotation_groups: Sequence[Tuple[str, List[str]]],
    selected_groups: Iterable[str] | None,
) -> List[Tuple[str, List[str]]]:
    if selected_groups is None:
        return list(rotation_groups)
    selected_set = {group.lower() for group in selected_groups}
    filtered = [
        (name, symbols)
        for name, symbols in rotation_groups
        if name.lower() in selected_set
    ]
    missing = sorted(selected_set - {name.lower() for name, _ in filtered})
    if missing:
        LOGGER.warning("ibkr.level2.groups_skipped", groups=missing)
    return filtered


def _select_client_id(connection_cfg: Mapping[str, object]) -> int:
    pool = connection_cfg.get("client_id_pool", [])
    if isinstance(pool, Sequence) and pool:
        return int(random.choice(pool))
    return int(connection_cfg.get("client_id_start", 101))


async def _connect(
    ib: IB,
    *,
    host: str,
    port: int,
    client_id: int,
    timeout: float,
    market_depth_type: str | None,
) -> None:
    LOGGER.info("ibkr.level2.connecting", host=host, port=port, client_id=client_id)
    connected = await ib.connectAsync(host, port, clientId=client_id, timeout=timeout)
    if not connected:
        raise RuntimeError("Unable to connect to Interactive Brokers API")
    if market_depth_type:
        ib.reqMarketDataType(int(market_depth_type))
    LOGGER.info("ibkr.level2.connected", client_id=client_id)


def _build_contract(symbol: str, overrides: Dict[str, Mapping[str, str]] | None) -> Stock:
    exchange = "SMART"
    currency = "USD"
    primary_exchange = None
    if overrides and symbol in overrides:
        override = overrides[symbol]
        exchange = override.get("exchange", exchange)
        currency = override.get("currency", currency)
        primary_exchange = override.get("primary_exchange")
    contract = Stock(symbol, exchange, currency, primaryExchange=primary_exchange)
    return contract


async def _process_group(
    ib: IB,
    redis_client,
    group_name: str,
    symbols: Sequence[str],
    config: Level2Config,
) -> None:
    active_symbols = list(symbols)[: config.max_concurrent_symbols]
    requested_at = datetime.now(timezone.utc)
    LOGGER.info(
        "ibkr.level2.group_start",
        group=group_name,
        symbols=active_symbols,
    )

    subscriptions: Dict[str, Ticker] = {}
    contracts: Dict[str, Stock] = {}

    try:
        for symbol in active_symbols:
            contract = _build_contract(symbol, config.contract_overrides)
            contracts[symbol] = contract
            ticker = ib.reqMktDepth(contract, numRows=config.depth_levels)
            subscriptions[symbol] = ticker

        await _wait_for_depth(ib, subscriptions, config.cadence_seconds)

        for symbol in active_symbols:
            ticker = subscriptions.get(symbol)
            if ticker is None:
                continue
            await _persist_depth(
                redis_client=redis_client,
                symbol=symbol,
                ticker=ticker,
                requested_at=requested_at,
                config=config,
                group_name=group_name,
            )
    except Exception as exc:  # pragma: no cover - runtime behaviour
        LOGGER.error("ibkr.level2.group_error", group=group_name, error=str(exc))
        for symbol in active_symbols:
            await _record_error(redis_client, symbol, config, requested_at, str(exc))
    finally:
        for symbol, ticker in subscriptions.items():
            try:
                ib.cancelMktDepth(ticker.contract)
            except Exception:  # pragma: no cover - best effort cleanup
                LOGGER.warning("ibkr.level2.cancel_failed", symbol=symbol)


async def _wait_for_depth(ib: IB, subscriptions: Mapping[str, Ticker], timeout: float) -> None:
    loop = asyncio.get_running_loop()
    start = loop.time()
    while True:
        if any(_has_dom_data(ticker) for ticker in subscriptions.values()):
            break
        if loop.time() - start > timeout:
            break
        await asyncio.sleep(0.1)
    remaining = max(timeout - (loop.time() - start), 0)
    if remaining:
        await asyncio.sleep(remaining)


async def _persist_depth(
    *,
    redis_client,
    symbol: str,
    ticker: Ticker,
    requested_at: datetime,
    config: Level2Config,
    group_name: str,
) -> None:
    heartbeat_key = config.heartbeat_pattern.format(symbol=symbol)
    redis_key = config.key_pattern.format(symbol=symbol)
    bids = _serialize_dom_levels(ticker.domBids, config.depth_levels)
    asks = _serialize_dom_levels(ticker.domAsks, config.depth_levels)
    payload = {
        "symbol": symbol,
        "source": "ibkr",
        "group": group_name,
        "requested_at": requested_at.isoformat(),
        "depth_levels": config.depth_levels,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "market_data_type": getattr(ticker, "marketDataType", None),
        "bids": bids,
        "asks": asks,
    }
    await store_json(redis_client, redis_key, payload, config.ttl_seconds)
    await set_heartbeat(
        redis_client,
        heartbeat_key,
        status="ok",
        timestamp=requested_at.isoformat(),
        extra={
            "group": group_name,
            "symbol_count": len(bids) + len(asks),
            "cadence_seconds": config.cadence_seconds,
        },
    )
    LOGGER.info("ibkr.level2.symbol_complete", symbol=symbol, group=group_name)


async def _record_error(
    redis_client,
    symbol: str,
    config: Level2Config,
    requested_at: datetime,
    error: str,
) -> None:
    await set_heartbeat(
        redis_client,
        config.heartbeat_pattern.format(symbol=symbol),
        status="error",
        timestamp=requested_at.isoformat(),
        extra={"error": error},
    )


def _has_dom_data(ticker: Ticker) -> bool:
    return bool(getattr(ticker, "domBids", None) or getattr(ticker, "domAsks", None))


def _serialize_dom_levels(levels, depth_limit: int) -> List[Dict[str, object]]:
    serialized: List[Dict[str, object]] = []
    if not levels:
        return serialized
    limit = max(depth_limit, 0) or 10
    for level in levels[:limit]:
        serialized.append(
            {
                "price": _maybe_float(getattr(level, "price", None)),
                "size": _maybe_float(getattr(level, "size", None)),
                "market_maker": getattr(level, "marketMaker", None),
                "time": getattr(level, "time", None),
            }
        )
    return serialized


def _maybe_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rotate IBKR level-2 subscriptions")
    parser.add_argument(
        "--group",
        dest="groups",
        action="append",
        help="Limit rotation to specific groups (repeatable)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    asyncio.run(run(args.groups))


__all__ = ["run", "parse_args", "main"]


if __name__ == "__main__":
    main()
