"""Capture execution and commission events from Interactive Brokers."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, Mapping, Sequence

import structlog

try:  # pragma: no cover
    from ib_insync import (
        CommissionReport,
        Execution,
        IB,
        OrderStatus,
    )  # type: ignore
except ImportError:  # pragma: no cover
    IB = Execution = CommissionReport = OrderStatus = None  # type: ignore
    _IMPORT_ERROR = sys.exc_info()[1]
else:  # pragma: no cover
    _IMPORT_ERROR = None

from src.core.redis import create_async_client, set_heartbeat
from src.core.settings import load_ibkr_config, load_runtime_config

LOGGER = structlog.get_logger()


@dataclass(slots=True)
class ExecutionConfig:
    stream: str
    maxlen: int
    last_key: str
    heartbeat_key: str
    include_commission: bool
    include_order_status: bool


async def run() -> None:
    if IB is None:
        raise RuntimeError(
            "ib-insync is required for IBKR execution ingestion. Install project requirements."
        ) from _IMPORT_ERROR

    runtime_config = load_runtime_config()
    ibkr_config = load_ibkr_config()
    exec_config = _parse_execution_config(ibkr_config)

    redis_client = create_async_client(runtime_config)
    ib = IB()
    connection_cfg = ibkr_config.get("connection", {})
    client_id = _select_client_id(connection_cfg)

    pending = _ExecutionBuffer(exec_config.include_commission, exec_config.include_order_status)

    try:
        await _connect(
            ib,
            host=connection_cfg.get("host", "127.0.0.1"),
            port=int(connection_cfg.get("port", 7497)),
            client_id=client_id,
            timeout=float(connection_cfg.get("connect_timeout_seconds", 10)),
        )

        listeners = _register_listeners(ib, pending)

        # Request all executions for the account
        LOGGER.info("ibkr.executions.requesting", note="Requesting all executions and orders")
        await ib.reqAllOpenOrdersAsync()
        executions = await ib.reqExecutionsAsync()
        LOGGER.info("ibkr.executions.received_historical", count=len(executions))
        # Process historical executions manually
        for trade in executions:
            if hasattr(trade, 'contract') and hasattr(trade, 'execution'):
                LOGGER.info("ibkr.execution.historical",
                           exec_id=getattr(trade.execution, "execId", "unknown"),
                           symbol=getattr(trade.contract, "symbol", "unknown"))
                pending.record_execution(trade.execution, trade.contract)
        await asyncio.sleep(1)  # Give time for any remaining events

        loop = asyncio.get_running_loop()
        flush_task = loop.create_task(
            _flush_loop(ib, redis_client, exec_config, pending)
        )
        await flush_task
    finally:
        for remover in listeners:
            remover()
        if ib.isConnected():
            ib.disconnect()
        await redis_client.aclose()


class _ExecutionBuffer:
    def __init__(self, include_commission: bool, include_order_status: bool) -> None:
        self.include_commission = include_commission
        self.include_order_status = include_order_status
        self.executions: Dict[str, Dict[str, object]] = {}

    def record_execution(self, exec_data: Execution, contract) -> None:
        exec_id = getattr(exec_data, "execId", None) or _random_id()
        payload = {
            "exec_id": exec_id,
            "contract": _serialize_contract(contract),
            "execution": _serialize_execution(exec_data),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self.include_order_status:
            payload["order_status"] = {}
        if self.include_commission:
            payload["commission_report"] = {}
        self.executions[exec_id] = payload

    def record_order_status(self, order_status: OrderStatus, contract, execution) -> None:
        if not self.include_order_status:
            return
        exec_id = getattr(execution, "execId", None)
        if not exec_id or exec_id not in self.executions:
            exec_id = _random_id()
            self.executions.setdefault(
                exec_id,
                {
                    "exec_id": exec_id,
                    "contract": _serialize_contract(contract),
                    "execution": {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        self.executions[exec_id]["order_status"] = _serialize_order_status(order_status)

    def record_commission(self, commission: CommissionReport) -> None:
        if not self.include_commission:
            return
        exec_id = getattr(commission, "execId", None)
        if not exec_id:
            return
        if exec_id not in self.executions:
            # DON'T create empty entries - this is a critical data loss bug
            LOGGER.error("ibkr.commission.no_execution",
                        exec_id=exec_id,
                        commission=getattr(commission, "commission", 0),
                        error="Commission arrived without execution - DISCARDING")
            return
        self.executions[exec_id]["commission_report"] = _serialize_commission(commission)

    def drain(self) -> Dict[str, Dict[str, object]]:
        drained = dict(self.executions)
        self.executions.clear()
        return drained


async def _flush_loop(ib: IB, redis_client, config: ExecutionConfig, buffer: _ExecutionBuffer) -> None:
    while True:
        await asyncio.sleep(1)
        if not buffer.executions:
            continue
        drained = buffer.drain()
        for exec_id, payload in drained.items():
            await redis_client.xadd(
                config.stream,
                fields={"data": json.dumps(payload)},
                maxlen=config.maxlen,
                approximate=True,
            )
            await redis_client.set(config.last_key, json.dumps(payload))
            await set_heartbeat(
                redis_client,
                config.heartbeat_key,
                status="ok",
                timestamp=datetime.now(timezone.utc).isoformat(),
                extra={"last_exec_id": exec_id, "buffered": len(drained)},
            )


def _parse_execution_config(config: Mapping[str, object]) -> ExecutionConfig:
    executions_cfg = config.get("executions", {})
    if not isinstance(executions_cfg, Mapping):
        raise ValueError("executions section missing in config/ibkr.yml")
    redis_cfg = executions_cfg.get("redis", {}) if isinstance(executions_cfg, Mapping) else {}
    return ExecutionConfig(
        stream=str(redis_cfg.get("stream", "stream:ibkr:executions")),
        maxlen=int(redis_cfg.get("maxlen", 5000)),
        last_key=str(redis_cfg.get("last_key", "raw:ibkr:execution:last")),
        heartbeat_key=str(redis_cfg.get("heartbeat", "state:ibkr:executions")),
        include_commission=bool(executions_cfg.get("include_commission", True)),
        include_order_status=bool(executions_cfg.get("include_order_status", True)),
    )


def _register_listeners(ib: IB, buffer: _ExecutionBuffer) -> Sequence[callable]:
    def exec_handler(trade, fill) -> None:
        LOGGER.info("ibkr.execution.received",
                   exec_id=getattr(fill.execution, "execId", "unknown"),
                   symbol=getattr(fill.contract, "symbol", "unknown"))
        buffer.record_execution(fill.execution, fill.contract)
        # Also record commission if present
        if fill.commissionReport and buffer.include_commission:
            buffer.record_commission(fill.commissionReport)

    def comm_handler(trade, fill, report: CommissionReport) -> None:
        LOGGER.warning("ibkr.commission.orphan",
                      exec_id=getattr(report, "execId", "unknown"),
                      note="Commission without execution - data loss!")
        # Try to capture contract/execution from fill
        if fill and fill.execution and fill.contract:
            buffer.record_execution(fill.execution, fill.contract)
        buffer.record_commission(report)

    ib.execDetailsEvent += exec_handler
    removers = [lambda: ib.execDetailsEvent.__isub__(exec_handler)]

    if buffer.include_commission:
        ib.commissionReportEvent += comm_handler
        removers.append(lambda: ib.commissionReportEvent.__isub__(comm_handler))

    if buffer.include_order_status:
        def status_handler(trade) -> None:
            fill = getattr(trade, "fills", [])[-1] if getattr(trade, "fills", []) else None
            if not fill:
                return
            buffer.record_order_status(trade.orderStatus, fill.contract, fill.execution)

        ib.orderStatusEvent += status_handler
        removers.append(lambda: ib.orderStatusEvent.__isub__(status_handler))

    return removers


async def _connect(
    ib: IB,
    *,
    host: str,
    port: int,
    client_id: int,
    timeout: float,
) -> None:
    LOGGER.info("ibkr.executions.connecting", host=host, port=port, client_id=client_id)
    connected = await ib.connectAsync(host, port, clientId=client_id, timeout=timeout)
    if not connected:
        raise RuntimeError("Unable to connect to Interactive Brokers API")
    LOGGER.info("ibkr.executions.connected", client_id=client_id)


def _select_client_id(connection_cfg: Mapping[str, object]) -> int:
    pool = connection_cfg.get("client_id_pool", [])
    if isinstance(pool, Sequence) and pool:
        return int(random.choice(pool))
    return int(connection_cfg.get("client_id_start", 101))


def _serialize_contract(contract) -> Mapping[str, object]:
    return {
        "con_id": getattr(contract, "conId", None),
        "symbol": getattr(contract, "symbol", None),
        "sec_type": getattr(contract, "secType", None),
        "currency": getattr(contract, "currency", None),
        "exchange": getattr(contract, "exchange", None),
        "primary_exchange": getattr(contract, "primaryExchange", None),
        "local_symbol": getattr(contract, "localSymbol", None),
    }


def _serialize_execution(exec_data: Execution) -> Mapping[str, object]:
    time_val = getattr(exec_data, "time", None)
    if hasattr(time_val, 'isoformat'):
        time_val = time_val.isoformat()
    elif time_val:
        time_val = str(time_val)

    return {
        "order_id": getattr(exec_data, "orderId", None),
        "client_id": getattr(exec_data, "clientId", None),
        "perm_id": getattr(exec_data, "permId", None),
        "side": getattr(exec_data, "side", None),
        "price": getattr(exec_data, "price", None),
        "avg_price": getattr(exec_data, "avgPrice", None),
        "shares": getattr(exec_data, "shares", None),
        "cum_qty": getattr(exec_data, "cumQty", None),
        "remain": getattr(exec_data, "remain", None),
        "time": time_val,
        "liquidity": getattr(exec_data, "liquidity", None),
        "order_ref": getattr(exec_data, "orderRef", None),
        "exchange": getattr(exec_data, "exchange", None),
        "exec_exchange": getattr(exec_data, "execExchange", None),
        "last_liquidity": getattr(exec_data, "lastLiquidity", None),
    }


def _serialize_commission(report: CommissionReport) -> Mapping[str, object]:
    return {
        "commission": getattr(report, "commission", None),
        "currency": getattr(report, "currency", None),
        "realized_pnl": getattr(report, "realizedPNL", None),
        "yield": getattr(report, "yield", None),
        "yield_redemption_date": getattr(report, "yieldRedemptionDate", None),
    }


def _serialize_order_status(status: OrderStatus) -> Mapping[str, object]:
    return {
        "status": getattr(status, "status", None),
        "filled": getattr(status, "filled", None),
        "remaining": getattr(status, "remaining", None),
        "avg_fill_price": getattr(status, "avgFillPrice", None),
        "last_fill_price": getattr(status, "lastFillPrice", None),
        "permid": getattr(status, "permid", None),
        "parent_id": getattr(status, "parentId", None),
        "why_held": getattr(status, "whyHeld", None),
        "mkt_cap_price": getattr(status, "mktCapPrice", None),
    }


def _random_id() -> str:
    return f"exec-{int(datetime.now(timezone.utc).timestamp() * 1_000_000):x}-{random.randint(1000, 9999)}"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture IBKR execution events")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    parse_args(argv)
    asyncio.run(run())


__all__ = ["run", "parse_args", "main"]


if __name__ == "__main__":
    main(None)
