"""Collect account summary, positions, and PnL from Interactive Brokers."""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, Sequence

import structlog

try:  # pragma: no cover - optional dependency guard
    from ib_insync import (
        AccountValue,
        IB,
        PnL,
        Position,
        PnLSingle,
    )
except ImportError:  # pragma: no cover
    IB = PnL = AccountValue = Position = PnLSingle = None  # type: ignore
    _IMPORT_ERROR = sys.exc_info()[1]
else:  # pragma: no cover
    _IMPORT_ERROR = None

from src.core.redis import create_async_client, set_heartbeat, store_json
from src.core.settings import load_ibkr_config, load_runtime_config

LOGGER = structlog.get_logger()
DEFAULT_ACCOUNT_CODE = "DU000000"


@dataclass(slots=True)
class SummaryConfig:
    cadence_seconds: int
    redis_key: str
    heartbeat_key: str
    ttl_seconds: int


@dataclass(slots=True)
class PositionsConfig:
    cadence_seconds: int
    redis_key: str
    heartbeat_key: str
    ttl_seconds: int
    asset_classes: Sequence[str]


@dataclass(slots=True)
class PnLConfig:
    cadence_seconds: int
    account_key: str
    heartbeat_key: str
    ttl_seconds: int
    position_pattern: str


@dataclass(slots=True)
class AccountBundleConfig:
    summary: SummaryConfig
    positions: PositionsConfig
    pnl: PnLConfig


async def run() -> None:
    if IB is None:
        raise RuntimeError(
            "ib-insync is required for IBKR account ingestion. Install project requirements."
        ) from _IMPORT_ERROR

    runtime_config = load_runtime_config()
    ibkr_config = load_ibkr_config()
    bundle = _parse_bundle_config(ibkr_config)

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
        )

        account_code = await _resolve_account_code(ib)
        await _collect_summary(ib, redis_client, bundle.summary, account_code)
        positions = await _collect_positions(ib, redis_client, bundle.positions, account_code)
        await _collect_pnl(ib, redis_client, bundle.pnl, account_code, positions)
    finally:
        if ib.isConnected():
            ib.disconnect()
        await redis_client.aclose()


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
) -> None:
    LOGGER.info("ibkr.account.connecting", host=host, port=port, client_id=client_id)
    connected = await ib.connectAsync(host, port, clientId=client_id, timeout=timeout)
    if not connected:
        raise RuntimeError("Unable to connect to Interactive Brokers API")
    LOGGER.info("ibkr.account.connected", client_id=client_id)


def _parse_bundle_config(config: Mapping[str, object]) -> AccountBundleConfig:
    bundle = config.get("account_bundle", {})
    if not isinstance(bundle, Mapping):
        raise ValueError("account_bundle section missing in config/ibkr.yml")

    summary_cfg = bundle.get("summary", {}) if isinstance(bundle, Mapping) else {}
    positions_cfg = bundle.get("positions", {}) if isinstance(bundle, Mapping) else {}
    pnl_cfg = bundle.get("pnl", {}) if isinstance(bundle, Mapping) else {}

    def _redis(mapping: Mapping[str, object], key: str, default: object) -> str:
        redis_cfg = mapping.get("redis", {}) if isinstance(mapping, Mapping) else {}
        value = redis_cfg.get(key, default)
        return str(value)

    return AccountBundleConfig(
        summary=SummaryConfig(
            cadence_seconds=int(summary_cfg.get("cadence_seconds", 15)),
            redis_key=_redis(summary_cfg, "key", "raw:ibkr:account:summary"),
            heartbeat_key=_redis(summary_cfg, "heartbeat", "state:ibkr:account:summary"),
            ttl_seconds=int((summary_cfg.get("redis", {}) or {}).get("ttl_seconds", 30)),
        ),
        positions=PositionsConfig(
            cadence_seconds=int(positions_cfg.get("cadence_seconds", 15)),
            redis_key=_redis(positions_cfg, "key", "raw:ibkr:account:positions"),
            heartbeat_key=_redis(positions_cfg, "heartbeat", "state:ibkr:account:positions"),
            ttl_seconds=int((positions_cfg.get("redis", {}) or {}).get("ttl_seconds", 30)),
            asset_classes=list(positions_cfg.get("include_asset_classes", [])),
        ),
        pnl=PnLConfig(
            cadence_seconds=int(pnl_cfg.get("cadence_seconds", 15)),
            account_key=_redis(pnl_cfg, "account_key", "raw:ibkr:account:pnl"),
            heartbeat_key=_redis(pnl_cfg, "heartbeat", "state:ibkr:account:pnl"),
            ttl_seconds=int((pnl_cfg.get("redis", {}) or {}).get("ttl_seconds", 30)),
            position_pattern=_redis(pnl_cfg, "position_pattern", "raw:ibkr:position:pnl:{symbol}"),
        ),
    )


async def _resolve_account_code(ib: IB) -> str:
    if hasattr(ib, "managedAccountsAsync"):
        accounts = await ib.managedAccountsAsync()
    else:  # pragma: no cover - compatibility fallback
        accounts = await asyncio.to_thread(ib.managedAccounts)
    return accounts[0] if accounts else DEFAULT_ACCOUNT_CODE


async def _collect_summary(
    ib: IB,
    redis_client,
    config: SummaryConfig,
    account_code: str,
) -> None:
    LOGGER.info("ibkr.account.summary.start", account=account_code)
    requested_at = datetime.now(timezone.utc)
    try:
        if hasattr(ib, "accountSummaryAsync"):
            rows: Sequence[AccountValue] = await ib.accountSummaryAsync(account_code)
        else:  # pragma: no cover - compatibility fallback
            rows = await asyncio.to_thread(ib.accountSummary, account_code)
        payload = _serialize_summary(account_code, rows, requested_at)
        await store_json(redis_client, config.redis_key, payload, config.ttl_seconds)
        await set_heartbeat(
            redis_client,
            config.heartbeat_key,
            status="ok",
            timestamp=requested_at.isoformat(),
            extra={"row_count": len(rows)},
        )
    except Exception as exc:
        LOGGER.error("ibkr.account.summary.error", error=str(exc))
        await set_heartbeat(
            redis_client,
            config.heartbeat_key,
            status="error",
            timestamp=requested_at.isoformat(),
            extra={"error": str(exc)},
        )


async def _collect_positions(
    ib: IB,
    redis_client,
    config: PositionsConfig,
    account_code: str,
) -> List[Position]:
    LOGGER.info("ibkr.account.positions.start", account=account_code)
    requested_at = datetime.now(timezone.utc)
    try:
        if hasattr(ib, "positionsAsync"):
            positions: Sequence[Position] = await ib.positionsAsync()
        else:  # pragma: no cover - compatibility fallback
            positions = await asyncio.to_thread(ib.positions)
        filtered = _filter_positions(positions, config.asset_classes, account_code)
        payload = _serialize_positions(account_code, filtered, requested_at)
        await store_json(redis_client, config.redis_key, payload, config.ttl_seconds)
        await set_heartbeat(
            redis_client,
            config.heartbeat_key,
            status="ok",
            timestamp=requested_at.isoformat(),
            extra={"position_count": len(filtered)},
        )
        return list(filtered)
    except Exception as exc:
        LOGGER.error("ibkr.account.positions.error", error=str(exc))
        await set_heartbeat(
            redis_client,
            config.heartbeat_key,
            status="error",
            timestamp=requested_at.isoformat(),
            extra={"error": str(exc)},
        )
        return []


async def _collect_pnl(
    ib: IB,
    redis_client,
    config: PnLConfig,
    account_code: str,
    positions: Sequence[Position],
) -> None:
    LOGGER.info("ibkr.account.pnl.start", account=account_code)
    requested_at = datetime.now(timezone.utc)
    try:
        account_pnl = await _await_account_pnl(ib, account_code)
        payload = _serialize_account_pnl(account_code, account_pnl, requested_at)
        await store_json(redis_client, config.account_key, payload, config.ttl_seconds)

        per_symbol: Dict[str, Mapping[str, object]] = {}
        for pos in positions:
            contract = getattr(pos, "contract", None)
            con_id = getattr(contract, "conId", None)
            symbol = getattr(contract, "symbol", None)
            if not con_id or not symbol:
                continue
            pnl_single = await _await_pnl_single(ib, account_code, con_id)
            per_symbol[symbol] = _serialize_pnl_single(symbol, pnl_single, requested_at)

        for symbol, data in per_symbol.items():
            redis_key = config.position_pattern.format(symbol=symbol)
            await store_json(redis_client, redis_key, data, config.ttl_seconds)

        await set_heartbeat(
            redis_client,
            config.heartbeat_key,
            status="ok",
            timestamp=requested_at.isoformat(),
            extra={"positions": len(per_symbol)},
        )
    except Exception as exc:
        LOGGER.error("ibkr.account.pnl.error", error=str(exc))
        await set_heartbeat(
            redis_client,
            config.heartbeat_key,
            status="error",
            timestamp=requested_at.isoformat(),
            extra={"error": str(exc)},
        )


async def _await_account_pnl(ib: IB, account_code: str) -> PnL:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[PnL] = loop.create_future()

    def handler(pnl: PnL) -> None:
        if getattr(pnl, "account", account_code) == account_code and not future.done():
            future.set_result(pnl)

    ib.pnlEvent += handler
    ib.reqPnL(account=account_code, modelCode="")
    try:
        await asyncio.sleep(0)
        return await asyncio.wait_for(future, timeout=5.0)
    finally:
        ib.pnlEvent -= handler
        ib.cancelPnL(account=account_code, modelCode="")


async def _await_pnl_single(ib: IB, account_code: str, con_id: int) -> PnLSingle:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[PnLSingle] = loop.create_future()

    def handler(pnl: PnLSingle) -> None:
        if getattr(pnl, "conId", 0) == con_id and not future.done():
            future.set_result(pnl)

    ib.pnlSingleEvent += handler
    ib.reqPnLSingle(account=account_code, modelCode="", conId=con_id)
    try:
        await asyncio.sleep(0)
        return await asyncio.wait_for(future, timeout=5.0)
    finally:
        ib.pnlSingleEvent -= handler
        ib.cancelPnLSingle(account=account_code, modelCode="", conId=con_id)


def _filter_positions(
    positions: Sequence[Position], asset_classes: Sequence[str], account_code: str
) -> List[Position]:
    filtered = [pos for pos in positions if getattr(pos, "account", account_code) == account_code]
    if not asset_classes:
        return list(filtered)
    allowed = {cls.upper() for cls in asset_classes}
    return [
        pos
        for pos in filtered
        if getattr(getattr(pos, "contract", None), "secType", "").upper() in allowed
    ]


def _serialize_summary(
    account: str, rows: Sequence[AccountValue], requested_at: datetime
) -> Mapping[str, object]:
    data = [
        {
            "tag": getattr(row, "tag", None),
            "value": getattr(row, "value", None),
            "currency": getattr(row, "currency", None),
        }
        for row in rows
    ]
    return {
        "account": account,
        "requested_at": requested_at.isoformat(),
        "values": data,
    }


def _serialize_positions(
    account: str, positions: Sequence[Position], requested_at: datetime
) -> Mapping[str, object]:
    rows = []
    for pos in positions:
        contract = getattr(pos, "contract", None)
        rows.append(
            {
                "symbol": getattr(contract, "symbol", None),
                "sec_type": getattr(contract, "secType", None),
                "currency": getattr(contract, "currency", None),
                "exchange": getattr(contract, "exchange", None),
                "position": _maybe_float(getattr(pos, "position", None)),
                "avg_cost": _maybe_float(getattr(pos, "avgCost", None)),
            }
        )
    return {
        "account": account,
        "requested_at": requested_at.isoformat(),
        "positions": rows,
    }


def _serialize_account_pnl(account: str, account_pnl: PnL, requested_at: datetime) -> Mapping[str, object]:
    return {
        "account": account,
        "requested_at": requested_at.isoformat(),
        "daily_pnl": _maybe_float(getattr(account_pnl, "dailyPnL", None)),
        "unrealized": _maybe_float(getattr(account_pnl, "unrealizedPnL", None)),
        "realized": _maybe_float(getattr(account_pnl, "realizedPnL", None)),
    }


def _serialize_pnl_single(symbol: str, pnl_single: PnLSingle, requested_at: datetime) -> Mapping[str, object]:
    return {
        "symbol": symbol,
        "requested_at": requested_at.isoformat(),
        "daily_pnl": _maybe_float(getattr(pnl_single, "dailyPnL", None)),
        "unrealized": _maybe_float(getattr(pnl_single, "unrealizedPnL", None)),
        "realized": _maybe_float(getattr(pnl_single, "realizedPnL", None)),
    }


def _maybe_float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect IBKR account summary/positions/PnL")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    parse_args(argv)
    asyncio.run(run())


__all__ = ["run", "parse_args", "main"]


if __name__ == "__main__":
    main(None)
