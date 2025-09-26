from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.ingestion.ibkr import level2


def test_parse_level2_config_reads_rotation() -> None:
    config = {
        "level2_depth": {
            "rotation_groups": {"grp1": ["NVDA", "AAPL"]},
            "depth_levels": 5,
            "cadence_seconds": 4,
            "max_concurrent_symbols": 2,
            "redis": {
                "key_pattern": "raw:ibkr:l2:{symbol}",
                "heartbeat_pattern": "state:ibkr:l2:{symbol}",
                "ttl_seconds": 12,
            },
            "request": {"market_depth_type": "2"},
        }
    }
    cfg = level2._parse_level2_config(config)  # type: ignore[attr-defined]
    assert cfg.depth_levels == 5
    assert cfg.cadence_seconds == 4
    assert cfg.max_concurrent_symbols == 2
    assert cfg.rotation_groups[0][0] == "grp1"
    assert cfg.rotation_groups[0][1] == ["NVDA", "AAPL"]
    assert cfg.key_pattern.endswith("{symbol}")
    assert cfg.market_depth_type == "2"


def test_resolve_rotation_filters_groups() -> None:
    rotation = [("grp1", ["AAPL"]), ("grp2", ["MSFT"])]
    filtered = level2._resolve_rotation(rotation, ["grp2"])  # type: ignore[attr-defined]
    assert filtered == [("grp2", ["MSFT"])]


def test_serialize_dom_levels_handles_objects() -> None:
    class StubLevel:
        def __init__(self, price, size, maker, stamp) -> None:
            self.price = price
            self.size = size
            self.marketMaker = maker
            self.time = stamp

    stamp = datetime(2025, 9, 27, 15, 30, tzinfo=timezone.utc)
    levels = [StubLevel(101.25, 5, "MM", stamp)]
    result = level2._serialize_dom_levels(levels, 5)  # type: ignore[attr-defined]
    assert result[0]["price"] == 101.25
    assert result[0]["market_maker"] == "MM"
    assert result[0]["time"] == stamp


def test_serialize_dom_levels_handles_none() -> None:
    assert level2._serialize_dom_levels(None, 5) == []  # type: ignore[attr-defined]


def test_build_contract_applies_overrides() -> None:
    if level2.Stock is None:  # type: ignore[attr-defined]
        pytest.skip("ib_insync not installed")
    overrides = {
        "NVDA": {"exchange": "ISLAND", "primary_exchange": "NASDAQ", "currency": "USD"}
    }
    contract = level2._build_contract("NVDA", overrides)  # type: ignore[attr-defined]
    assert contract.exchange == "ISLAND"
    assert contract.primaryExchange == "NASDAQ"
import pytest
