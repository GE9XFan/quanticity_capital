from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingestion.alpha_vantage.bbands import build_storage_record


@pytest.fixture(scope="module")
def sample_payload() -> dict:
    sample_path = Path("docs/samples/alpha_vantage/bbands/IBM.json")
    with sample_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_build_storage_record_structure(sample_payload: dict) -> None:
    now = datetime(2025, 9, 26, 9, 15, tzinfo=timezone.utc)
    record = build_storage_record(
        symbol="AAPL",
        endpoint_name="BBANDS",
        ttl_seconds=300,
        request_params={
            "function": "BBANDS",
            "symbol": "AAPL",
            "interval": "1min",
            "time_period": 20,
            "series_type": "close",
            "nbdevup": 2,
            "nbdevdn": 2,
            "matype": 0,
        },
        data=sample_payload,
        requested_at=now,
    )

    assert record["symbol"] == "AAPL"
    assert record["endpoint"] == "BBANDS"
    assert record["ttl_applied"] == 300
    assert record["requested_at"] == now.isoformat()
    assert record["data"] == sample_payload
    assert record["request_params"]["time_period"] == 20
    assert record["request_params"]["nbdevdn"] == 2


def test_build_storage_record_preserves_request_params(sample_payload: dict) -> None:
    params = {"function": "BBANDS", "symbol": "SPY"}
    record = build_storage_record(
        symbol="SPY",
        endpoint_name="BBANDS",
        ttl_seconds=300,
        request_params=params,
        data=sample_payload,
    )

    params["symbol"] = "QQQ"
    assert record["request_params"]["symbol"] == "SPY"
