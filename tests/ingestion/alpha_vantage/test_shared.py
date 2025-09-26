from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Mapping

import pytest

from src.ingestion.alpha_vantage._shared import (
    AlphaVantageIngestionRunner,
    PayloadValidationError,
)


class FakeResponse:
    def __init__(
        self,
        payload: Dict[str, Any] | None = None,
        *,
        text: str | None = None,
        status_code: int = 200,
    ) -> None:
        self._payload = payload
        self._text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:  # pragma: no cover - only used for non-200 paths
        if self.status_code >= 400:
            raise AssertionError("Unexpected non-200 status during test")

    def json(self) -> Dict[str, Any]:
        if self._payload is None:
            raise ValueError("No JSON payload configured")
        return self._payload

    @property
    def text(self) -> str:
        return self._text or ""


@pytest.fixture
def runner_env(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    writes: list[Dict[str, Any]] = []
    heartbeats: list[Dict[str, Any]] = []

    class FakeRedisClient:
        async def aclose(self) -> None:
            return None

    fake_redis = FakeRedisClient()
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-key")

    runtime_config: dict[str, Any] = {}
    endpoint_config: dict[str, Any] = {
        "function": "TEST_FUNC",
        "symbols": ["SPY", "QQQ"],
        "params": {"interval": "1min"},
        "cadence_seconds": 15,
        "redis": {
            "key_pattern": "raw:alpha_vantage:test_endpoint:{symbol}",
            "ttl_seconds": 30,
        },
    }
    alpha_config: dict[str, Any] = {
        "defaults": {
            "api_url": "https://example.com",
            "request": {"max_attempts": 1, "backoff_seconds": [0]},
            "redis": {
                "key_prefix": "raw:alpha_vantage",
                "heartbeat_prefix": "state:alpha_vantage",
            },
        },
        "endpoints": {"test_endpoint": endpoint_config},
    }

    def fake_load_configuration() -> tuple[dict[str, Any], dict[str, Any]]:
        return runtime_config, alpha_config

    monkeypatch.setattr(
        "src.ingestion.alpha_vantage._shared.load_configuration",
        fake_load_configuration,
    )
    monkeypatch.setattr(
        "src.ingestion.alpha_vantage._shared.create_async_client",
        lambda runtime_config: fake_redis,
    )

    async def fake_store_json(client, key: str, payload: Dict[str, Any], ttl: int | None) -> None:
        writes.append({"key": key, "payload": payload, "ttl": ttl})

    async def fake_set_heartbeat(
        client,
        key: str,
        status: str,
        timestamp: str,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        heartbeats.append({"key": key, "status": status, "extra": extra or {}})

    monkeypatch.setattr(
        "src.ingestion.alpha_vantage._shared.store_json",
        fake_store_json,
    )
    monkeypatch.setattr(
        "src.ingestion.alpha_vantage._shared.set_heartbeat",
        fake_set_heartbeat,
    )

    class FakeHttpClient:
        async def __aenter__(self) -> "FakeHttpClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

    monkeypatch.setattr(
        "src.ingestion.alpha_vantage._shared.create_http_client",
        lambda timeout: FakeHttpClient(),
    )

    def set_response(
        payload: Dict[str, Any] | None,
        status_code: int = 200,
        *,
        text: str | None = None,
    ) -> Dict[str, Any]:
        response = FakeResponse(payload=payload, text=text, status_code=status_code)
        capture: Dict[str, Any] = {"retry_codes": None, "params": []}

        async def fake_request_with_backoff(
            client,
            method: str,
            url: str,
            *,
            params: Dict[str, Any],
            max_attempts: int,
            backoff_seconds,
            retry_status_codes,
        ) -> FakeResponse:
            capture["retry_codes"] = tuple(retry_status_codes or ())
            capture["params"].append(dict(params))
            return response

        monkeypatch.setattr(
            "src.ingestion.alpha_vantage._shared.request_with_backoff",
            fake_request_with_backoff,
        )
        return capture

    def make_runner(validator: Callable[[Mapping[str, Any], str], Mapping[str, Any]]) -> AlphaVantageIngestionRunner:
        return AlphaVantageIngestionRunner(slug="test_endpoint", validator=validator)

    return {
        "set_response": set_response,
        "make_runner": make_runner,
        "writes": writes,
        "heartbeats": heartbeats,
        "endpoint_config": endpoint_config,
    }


def test_runner_persists_payload_success(runner_env: Dict[str, Any]) -> None:
    capture = runner_env["set_response"]({"data": {"value": 42}})
    runner = runner_env["make_runner"](lambda payload, symbol: payload)

    asyncio.run(runner.run(["SPY"]))

    assert capture["retry_codes"] == (429,)
    assert capture["params"] == [
        {"function": "TEST_FUNC", "interval": "1min", "symbol": "SPY", "apikey": "test-key"}
    ]

    writes = runner_env["writes"]
    assert len(writes) == 1
    assert writes[0]["key"] == "raw:alpha_vantage:test_endpoint:SPY"
    assert writes[0]["payload"]["endpoint"] == "TEST_FUNC"

    heartbeats = runner_env["heartbeats"]
    assert heartbeats[-1]["status"] == "ok"


def test_runner_request_param_overrides(runner_env: Dict[str, Any]) -> None:
    capture = runner_env["set_response"]({"data": {"value": 1}})
    runner = runner_env["make_runner"](lambda payload, symbol: payload)

    asyncio.run(
        runner.run(["SPY"], request_param_overrides={"interval": "daily", "window": 10})
    )

    params = capture["params"][0]
    assert params["interval"] == "daily"
    assert params["window"] == 10


def test_runner_formats_key_with_request_fields(runner_env: Dict[str, Any]) -> None:
    endpoint_config = runner_env["endpoint_config"]
    original_pattern = endpoint_config["redis"]["key_pattern"]
    original_params = dict(endpoint_config.get("params", {}))
    heartbeats = runner_env["heartbeats"]
    try:
        endpoint_config["redis"]["key_pattern"] = (
            "raw:alpha_vantage:test_endpoint:{symbol}:{year}Q{quarter}"
        )
        endpoint_config.setdefault("params", {})["year"] = 2025
        endpoint_config["params"]["quarter"] = 3

        runner = runner_env["make_runner"](lambda payload, symbol: payload)
        runner_env["set_response"]({"data": {"value": 1}})

        asyncio.run(runner.run(["SPY"]))

        writes = runner_env["writes"]
        assert writes[-1]["key"].endswith(":2025Q3")
    finally:
        endpoint_config["redis"]["key_pattern"] = original_pattern
        endpoint_config["params"] = original_params
    assert heartbeats[-1]["extra"]["ttl_seconds"] == 30


def test_runner_parses_csv_response(runner_env: Dict[str, Any]) -> None:
    endpoint_config = runner_env["endpoint_config"]
    endpoint_config["request"] = {
        "include_symbol": False,
        "response_format": "csv",
        "csv_root_key": "earningsCalendar",
    }
    endpoint_config["symbols"] = ["GLOBAL"]
    endpoint_config["redis"] = {
        "key_pattern": "raw:alpha_vantage:earnings_calendar",
        "ttl_seconds": 86400,
    }

    csv_text = "symbol,reportDate,estimate\nNVDA,2025-11-20,7.05\n"
    runner_env["set_response"](None, text=csv_text)
    runner = runner_env["make_runner"](lambda payload, symbol: payload)

    asyncio.run(runner.run(["GLOBAL"]))

    writes = runner_env["writes"]
    assert writes[-1]["payload"]["data"]["earningsCalendar"][0]["symbol"] == "NVDA"


@pytest.mark.parametrize(
    "message_key, expected_reason",
    [
        ("Note", "note"),
        ("Information", "information"),
        ("Error Message", "error_message"),
    ],
)
def test_runner_handles_informational_payloads(
    runner_env: Dict[str, Any], message_key: str, expected_reason: str
) -> None:
    capture = runner_env["set_response"]({message_key: "Throttle"})
    runner = runner_env["make_runner"](lambda payload, symbol: payload)

    asyncio.run(runner.run(["SPY"]))

    assert capture["retry_codes"] == (429,)
    assert runner_env["writes"] == []

    heartbeats = runner_env["heartbeats"]
    assert heartbeats[-1]["status"] == "error"
    assert heartbeats[-1]["extra"]["error"] == expected_reason
    assert heartbeats[-1]["extra"]["message"] == "Throttle"


def test_runner_handles_validator_failure(runner_env: Dict[str, Any]) -> None:
    runner_env["set_response"]({"data": {"value": 100}})

    def bad_validator(payload: Mapping[str, Any], symbol: str) -> Mapping[str, Any]:
        raise PayloadValidationError(
            "bad-payload",
            reason="validation-failed",
            extra={"detail": "missing field"},
        )

    runner = runner_env["make_runner"](bad_validator)

    asyncio.run(runner.run(["SPY"]))

    assert runner_env["writes"] == []
    heartbeats = runner_env["heartbeats"]
    assert heartbeats[-1]["status"] == "error"
    assert heartbeats[-1]["extra"]["error"] == "validation-failed"
    assert heartbeats[-1]["extra"]["detail"] == "missing field"


def test_runner_skips_symbol_when_disabled(runner_env: Dict[str, Any]) -> None:
    runner_env["writes"].clear()
    runner_env["heartbeats"].clear()
    runner_env["endpoint_config"]["request"] = {"include_symbol": False}
    runner_env["endpoint_config"]["symbols"] = ["MARKET"]
    runner_env["endpoint_config"]["redis"] = {
        "key_pattern": "raw:alpha_vantage:test_endpoint:{symbol}",
        "ttl_seconds": 15,
    }

    capture = runner_env["set_response"]({"top_gainers": [1], "top_losers": [1], "most_actively_traded": [1], "metadata": "ok"})
    runner = runner_env["make_runner"](lambda payload, symbol: payload)

    asyncio.run(runner.run(["MARKET"]))

    assert capture["params"] == [
        {"function": "TEST_FUNC", "interval": "1min", "apikey": "test-key"}
    ]

    writes = runner_env["writes"]
    assert len(writes) == 1
    assert writes[0]["key"] == "raw:alpha_vantage:test_endpoint:MARKET"


def test_runner_uses_custom_symbol_param(runner_env: Dict[str, Any]) -> None:
    runner_env["writes"].clear()
    runner_env["heartbeats"].clear()
    runner_env["endpoint_config"]["request"] = {"include_symbol": True, "symbol_param": "tickers"}
    runner_env["endpoint_config"]["symbols"] = ["AAPL"]

    capture = runner_env["set_response"]({"feed": [{"ticker_sentiment": [], "title": "t", "url": "u", "time_published": "2025", "overall_sentiment_score": 0.0}]})
    runner = runner_env["make_runner"](lambda payload, symbol: payload)

    asyncio.run(runner.run(["AAPL"]))

    assert capture["params"] == [
        {"function": "TEST_FUNC", "interval": "1min", "tickers": "AAPL", "apikey": "test-key"}
    ]
