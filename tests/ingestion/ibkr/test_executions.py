from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.ingestion.ibkr import executions


def test_parse_execution_config_defaults() -> None:
    config = {
        "executions": {
            "redis": {"stream": "stream:ibkr:executions", "maxlen": 1234, "last_key": "last"},
            "include_commission": False,
        }
    }
    cfg = executions._parse_execution_config(config)  # type: ignore[attr-defined]
    assert cfg.stream == "stream:ibkr:executions"
    assert cfg.maxlen == 1234
    assert not cfg.include_commission


def test_execution_buffer_drain() -> None:
    buffer = executions._ExecutionBuffer(include_commission=True, include_order_status=True)  # type: ignore[attr-defined]

    class StubExecution:
        execId = "1"
        orderId = 123
        clientId = 456
        permId = 789
        side = "BUY"
        price = 10.5
        avgPrice = 10.4
        shares = 1
        cumQty = 1
        remain = 0
        time = "2025-09-27 12:00:00"
        liquidity = 1
        orderRef = "ref"
        exchange = "SMART"
        execExchange = "ISLAND"
        lastLiquidity = 2

    class StubContract:
        conId = 1
        symbol = "NVDA"
        secType = "STK"
        currency = "USD"
        exchange = "SMART"
        primaryExchange = "NASDAQ"
        localSymbol = "NVDA"

    buffer.record_execution(StubExecution(), StubContract())
    drained = buffer.drain()
    assert drained
    exec_id, payload = drained.popitem()
    assert payload["contract"]["symbol"] == "NVDA"
    assert payload["execution"]["order_id"] == 123


def test_serialize_commission() -> None:
    class StubCommission:
        commission = 1.23
        currency = "USD"
        realizedPNL = 0.5
        yield_ = None
        yieldRedemptionDate = "20250930"

    serialized = executions._serialize_commission(StubCommission())  # type: ignore[attr-defined]
    assert serialized["commission"] == 1.23
    assert serialized["currency"] == "USD"


def test_random_id_format() -> None:
    exec_id = executions._random_id()  # type: ignore[attr-defined]
    assert exec_id.startswith("exec-")
