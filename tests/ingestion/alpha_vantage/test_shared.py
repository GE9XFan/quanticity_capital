from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Mapping

import pytest

from src.ingestion.alpha_vantage._shared import (
    AlphaVantageIngestionRunner,
    PayloadValidationError,
)


class FakeResponse:
    def __init__(self, payload: Dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:  # pragma: no cover - only used for non-200 paths
        if self.status_code >= 400:
            raise AssertionError("Unexpected non-200 status during test")

    def json(self) -> Dict[str, Any]:
        return self._payload


@pytest.fixture
def runner_env(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    writes: list[Dict[str, Any]] = []
    heartbeats: list[Dict[str, Any]] = []

    class FakeRedisClient:
        async def aclose(self) -> None:
            return None

    fake_redis = FakeRedisClient()
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-key")

    def fake_load_configuration() -> tuple[dict[str, Any], dict[str, Any]]:
        runtime_config: dict[str, Any] = {}
        alpha_config: dict[str, Any] = {
            "defaults": {
                "api_url": "https://example.com",
                "request": {"max_attempts": 1, "backoff_seconds": [0]},
                "redis": {
                    "key_prefix": "raw:alpha_vantage",
                    "heartbeat_prefix": "state:alpha_vantage",
                },
            },
            "endpoints": {
                "test_endpoint": {
                    "function": "TEST_FUNC",
                    "symbols": ["SPY", "QQQ"],
                    "params": {"interval": "1min"},
                    "cadence_seconds": 15,
                    "redis": {
                        "key_pattern": "raw:alpha_vantage:test_endpoint:{symbol}",
                        "ttl_seconds": 30,
                    },
                }
            },
        }
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

    def set_response(payload: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
        response = FakeResponse(payload=payload, status_code=status_code)
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
    assert heartbeats[-1]["extra"]["ttl_seconds"] == 30


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
