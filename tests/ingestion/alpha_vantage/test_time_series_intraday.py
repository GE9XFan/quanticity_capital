from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingestion.alpha_vantage.time_series_intraday import build_storage_record


@pytest.fixture(scope="module")
def sample_payload() -> dict:
    sample_path = Path("docs/samples/alpha_vantage/time_series_intraday/IBM.json")
    with sample_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_build_storage_record_structure(sample_payload: dict) -> None:
    now = datetime(2025, 9, 26, 10, 0, tzinfo=timezone.utc)
    record = build_storage_record(
        symbol="SPY",
        endpoint_name="TIME_SERIES_INTRADAY",
        ttl_seconds=60,
        request_params={
            "function": "TIME_SERIES_INTRADAY",
            "symbol": "SPY",
            "interval": "1min",
            "outputsize": "full",
            "extended_hours": "true",
        },
        data=sample_payload,
        requested_at=now,
    )

    assert record["symbol"] == "SPY"
    assert record["endpoint"] == "TIME_SERIES_INTRADAY"
    assert record["ttl_applied"] == 60
    assert record["requested_at"] == now.isoformat()
    assert record["data"] == sample_payload
    assert record["request_params"]["interval"] == "1min"
    assert record["request_params"]["extended_hours"] == "true"


def test_build_storage_record_copies_request_params(sample_payload: dict) -> None:
    params = {"function": "TIME_SERIES_INTRADAY", "symbol": "IBM"}
    record = build_storage_record(
        symbol="IBM",
        endpoint_name="TIME_SERIES_INTRADAY",
        ttl_seconds=60,
        request_params=params,
        data=sample_payload,
    )

    params["symbol"] = "MSFT"
    assert record["request_params"]["symbol"] == "IBM"
