from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.ingestion.ibkr import account


def test_parse_bundle_config_defaults() -> None:
    config = {
        "account_bundle": {
            "summary": {"redis": {"key": "summary", "heartbeat": "hb", "ttl_seconds": 20}},
            "positions": {
                "cadence_seconds": 10,
                "include_asset_classes": ["STK"],
                "redis": {"key": "positions", "heartbeat": "positions_hb", "ttl_seconds": 25},
            },
            "pnl": {
                "redis": {
                    "account_key": "account_pnl",
                    "heartbeat": "pnl_hb",
                    "ttl_seconds": 35,
                    "position_pattern": "position_pnl:{symbol}",
                }
            },
        }
    }
    cfg = account._parse_bundle_config(config)  # type: ignore[attr-defined]
    assert cfg.summary.redis_key == "summary"
    assert cfg.positions.asset_classes == ["STK"]
    assert cfg.pnl.position_pattern == "position_pnl:{symbol}"


def test_filter_positions_filters_by_account_and_asset() -> None:
    class StubContract:
        def __init__(self, symbol: str, sec_type: str) -> None:
            self.symbol = symbol
            self.secType = sec_type
            self.currency = "USD"
            self.exchange = "SMART"

    class StubPosition:
        def __init__(self, symbol: str, account_code: str, sec_type: str) -> None:
            self.contract = StubContract(symbol, sec_type)
            self.account = account_code
            self.position = 5
            self.avgCost = 120.5

    positions = [
        StubPosition("NVDA", "DU123", "STK"),
        StubPosition("ESZ5", "DU123", "FUT"),
        StubPosition("AAPL", "DU999", "STK"),
    ]
    filtered = account._filter_positions(positions, ["STK"], "DU123")  # type: ignore[attr-defined]
    assert len(filtered) == 1
    assert filtered[0].contract.symbol == "NVDA"


def test_serialize_summary_formats_rows() -> None:
    class StubSummary:
        def __init__(self) -> None:
            self.tag = "TotalCashValue"
            self.value = "12345"
            self.currency = "USD"

    now = datetime(2025, 9, 27, 15, 0, tzinfo=timezone.utc)
    payload = account._serialize_summary("DU123", [StubSummary()], now)  # type: ignore[attr-defined]
    assert payload["account"] == "DU123"
    assert payload["values"][0]["tag"] == "TotalCashValue"


def test_serialize_account_pnl_handles_missing() -> None:
    class StubPnL:
        dailyPnL = None
        unrealizedPnL = 100.5
        realizedPnL = -5.25

    now = datetime(2025, 9, 27, 15, 0, tzinfo=timezone.utc)
    payload = account._serialize_account_pnl("DU123", StubPnL(), now)  # type: ignore[attr-defined]
    assert payload["daily_pnl"] is None
    assert payload["unrealized"] == pytest.approx(100.5)
    assert payload["realized"] == pytest.approx(-5.25)


def test_serialize_pnl_single() -> None:
    class StubSingle:
        dailyPnL = 10
        unrealizedPnL = 5
        realizedPnL = 2

    now = datetime(2025, 9, 27, 15, 0, tzinfo=timezone.utc)
    payload = account._serialize_pnl_single("NVDA", StubSingle(), now)  # type: ignore[attr-defined]
    assert payload["symbol"] == "NVDA"
    assert payload["daily_pnl"] == 10


def test_maybe_float_handles_errors() -> None:
    assert account._maybe_float("123.45") == pytest.approx(123.45)  # type: ignore[attr-defined]
    assert account._maybe_float("not-a-number") is None  # type: ignore[attr-defined]
