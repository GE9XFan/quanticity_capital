from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingestion.alpha_vantage.top_gainers_losers import build_storage_record


@pytest.fixture(scope="module")
def sample_payload() -> dict:
    sample_path = Path("docs/samples/alpha_vantage/top_gainers_losers/sample.json")
    with sample_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_build_storage_record_structure(sample_payload: dict) -> None:
    now = datetime(2025, 9, 27, 12, 0, tzinfo=timezone.utc)
    record = build_storage_record(
        symbol="MARKET",
        endpoint_name="TOP_GAINERS_LOSERS",
        ttl_seconds=300,
        request_params={"function": "TOP_GAINERS_LOSERS"},
        data=sample_payload,
        requested_at=now,
    )

    assert record["symbol"] == "MARKET"
    assert record["endpoint"] == "TOP_GAINERS_LOSERS"
    assert record["ttl_applied"] == 300
    assert record["requested_at"] == now.isoformat()
    assert record["data"] == sample_payload
    assert record["request_params"]["function"] == "TOP_GAINERS_LOSERS"


def test_build_storage_record_copies_request_params(sample_payload: dict) -> None:
    params = {"function": "TOP_GAINERS_LOSERS"}
    record = build_storage_record(
        symbol="MARKET",
        endpoint_name="TOP_GAINERS_LOSERS",
        ttl_seconds=300,
        request_params=params,
        data=sample_payload,
    )

    params["function"] = "OTHER"
    assert record["request_params"]["function"] == "TOP_GAINERS_LOSERS"
