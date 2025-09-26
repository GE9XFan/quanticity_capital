from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingestion.alpha_vantage.macd import build_storage_record


@pytest.fixture(scope="module")
def sample_payload() -> dict:
    sample_path = Path("docs/samples/alpha_vantage/macd/USDEUR.json")
    with sample_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_build_storage_record_structure(sample_payload: dict) -> None:
    now = datetime(2025, 9, 26, 9, 0, tzinfo=timezone.utc)
    record = build_storage_record(
        symbol="TSLA",
        endpoint_name="MACD",
        ttl_seconds=300,
        request_params={
            "function": "MACD",
            "symbol": "TSLA",
            "interval": "1min",
            "series_type": "close",
            "fastperiod": 12,
            "slowperiod": 26,
            "signalperiod": 9,
        },
        data=sample_payload,
        requested_at=now,
    )

    assert record["symbol"] == "TSLA"
    assert record["endpoint"] == "MACD"
    assert record["ttl_applied"] == 300
    assert record["requested_at"] == now.isoformat()
    assert record["data"] == sample_payload
    assert record["request_params"]["function"] == "MACD"
    assert record["request_params"]["signalperiod"] == 9


def test_build_storage_record_immutable_request_params(sample_payload: dict) -> None:
    params = {"function": "MACD", "symbol": "SPY"}
    record = build_storage_record(
        symbol="SPY",
        endpoint_name="MACD",
        ttl_seconds=300,
        request_params=params,
        data=sample_payload,
    )

    params["symbol"] = "QQQ"
    assert record["request_params"]["symbol"] == "SPY"
