from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingestion.alpha_vantage.realtime_options import build_storage_record


@pytest.fixture(scope="module")
def sample_payload() -> dict:
    sample_path = Path("docs/samples/alpha_vantage/realtime_options/TSLA.json")
    with sample_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_build_storage_record_structure(sample_payload: dict) -> None:
    now = datetime(2025, 9, 26, 8, 30, tzinfo=timezone.utc)
    record = build_storage_record(
        symbol="TSLA",
        endpoint_name="REALTIME_OPTIONS",
        ttl_seconds=30,
        request_params={"function": "REALTIME_OPTIONS", "symbol": "TSLA", "require_greeks": True},
        data=sample_payload,
        requested_at=now,
    )

    assert record["symbol"] == "TSLA"
    assert record["endpoint"] == "REALTIME_OPTIONS"
    assert record["ttl_applied"] == 30
    assert record["requested_at"] == now.isoformat()
    assert record["data"] == sample_payload
    assert record["request_params"]["function"] == "REALTIME_OPTIONS"
    assert record["request_params"]["symbol"] == "TSLA"


def test_build_storage_record_copies_request_params(sample_payload: dict) -> None:
    request_params = {"function": "REALTIME_OPTIONS", "symbol": "TSLA"}
    record = build_storage_record(
        symbol="TSLA",
        endpoint_name="REALTIME_OPTIONS",
        ttl_seconds=30,
        request_params=request_params,
        data=sample_payload,
    )

    request_params["symbol"] = "SPY"
    assert record["request_params"]["symbol"] == "TSLA"
