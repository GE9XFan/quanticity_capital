from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingestion.alpha_vantage.vwap import build_storage_record


@pytest.fixture(scope="module")
def sample_payload() -> dict:
    sample_path = Path("docs/samples/alpha_vantage/vwap/IBM.json")
    with sample_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_build_storage_record_structure(sample_payload: dict) -> None:
    now = datetime(2025, 9, 26, 8, 45, tzinfo=timezone.utc)
    record = build_storage_record(
        symbol="SPY",
        endpoint_name="VWAP",
        ttl_seconds=300,
        request_params={"function": "VWAP", "symbol": "SPY", "interval": "1min"},
        data=sample_payload,
        requested_at=now,
    )

    assert record["symbol"] == "SPY"
    assert record["endpoint"] == "VWAP"
    assert record["ttl_applied"] == 300
    assert record["requested_at"] == now.isoformat()
    assert record["data"] == sample_payload
    assert record["request_params"]["function"] == "VWAP"
    assert record["request_params"]["interval"] == "1min"


def test_build_storage_record_copies_request_params(sample_payload: dict) -> None:
    params = {"function": "VWAP", "symbol": "QQQ"}
    record = build_storage_record(
        symbol="QQQ",
        endpoint_name="VWAP",
        ttl_seconds=300,
        request_params=params,
        data=sample_payload,
    )

    params["symbol"] = "IWM"
    assert record["request_params"]["symbol"] == "QQQ"
