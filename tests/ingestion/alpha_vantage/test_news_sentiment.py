from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingestion.alpha_vantage.news_sentiment import build_storage_record


@pytest.fixture(scope="module")
def sample_payload() -> dict:
    sample_path = Path("docs/samples/alpha_vantage/news_sentiment/sample.json")
    with sample_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_build_storage_record_structure(sample_payload: dict) -> None:
    now = datetime(2025, 9, 27, 13, 0, tzinfo=timezone.utc)
    record = build_storage_record(
        symbol="AAPL",
        endpoint_name="NEWS_SENTIMENT",
        ttl_seconds=900,
        request_params={
            "function": "NEWS_SENTIMENT",
            "tickers": "AAPL",
            "limit": 50,
            "sort": "LATEST",
        },
        data=sample_payload,
        requested_at=now,
    )

    assert record["symbol"] == "AAPL"
    assert record["endpoint"] == "NEWS_SENTIMENT"
    assert record["ttl_applied"] == 900
    assert record["requested_at"] == now.isoformat()
    assert record["data"] == sample_payload
    assert record["request_params"]["tickers"].startswith("AAPL")


def test_build_storage_record_preserves_request_params(sample_payload: dict) -> None:
    params = {"function": "NEWS_SENTIMENT", "tickers": "AAPL"}
    record = build_storage_record(
        symbol="AAPL",
        endpoint_name="NEWS_SENTIMENT",
        ttl_seconds=900,
        request_params=params,
        data=sample_payload,
    )

    params["tickers"] = "MSFT"
    assert record["request_params"]["tickers"] == "AAPL"
