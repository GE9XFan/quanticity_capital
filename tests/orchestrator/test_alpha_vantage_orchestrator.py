"""Tests for the Alpha Vantage orchestrator."""

from __future__ import annotations

import json
from collections import deque
from typing import Any, Dict, Iterable, Mapping

import pytest

from quanticity_capital.orchestrator import AlphaVantageOrchestrator
from quanticity_capital.runner import RunnerResult


class FakeAlphaVantageClient:
    """Fake client that yields pre-seeded responses and records calls."""

    def __init__(self, responses: Iterable[Any]) -> None:
        self._responses = deque(responses)
        self.calls: list[Dict[str, Any]] = []

    def fetch(self, params: Mapping[str, Any]) -> Any:
        self.calls.append(dict(params))
        if not self._responses:
            raise AssertionError("Unexpected Alpha Vantage request")
        payload = self._responses.popleft()
        if isinstance(payload, Exception):
            raise payload
        return payload


class FakeRedis:
    """In-memory Redis stub capturing payloads and TTL semantics."""

    def __init__(self) -> None:
        self.storage: Dict[str, Dict[str, Any]] = {}
        self.calls: list[Dict[str, Any]] = []

    def set(self, name: str, value: str, ex: int | None = None) -> bool:
        self.storage[name] = {"value": value, "ttl": ex}
        self.calls.append({"name": name, "ttl": ex})
        return True

    def ttl(self, name: str) -> int:
        if name not in self.storage:
            return -2
        ttl = self.storage[name].get("ttl")
        if ttl is None:
            return -1
        return int(ttl)

    def close(self) -> None:
        return None


def build_settings(extra: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    base = {
        "services": {
            "alphavantage": {
                "base_url": "https://www.alphavantage.co",
                "api_key_env": "ALPHAVANTAGE_API_KEY",
            }
        },
        "ingestion": {
            "alpha_vantage": {
                "enabled_endpoints": ["EARNINGS_CALL_TRANSCRIPT"],
                "endpoints": {
                    "EARNINGS_CALL_TRANSCRIPT": {
                        "contexts": [
                            {"symbol": "NVDA", "quarter": "2024Q3"},
                        ]
                    }
                },
            }
        },
    }
    if extra:
        base.update(extra)
    return base


def test_orchestrator_dispatches_jobs_with_context_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_env = {"ALPHAVANTAGE_API_KEY": "test-key"}
    client = FakeAlphaVantageClient([
        {"data": {"value": 1}},
    ])

    orchestrator = AlphaVantageOrchestrator(
        settings=build_settings(),
        env=fake_env,
        client=client,
        persist_results=False,
    )

    plan = orchestrator.build_job_plan()
    assert set(plan) == {"EARNINGS_CALL_TRANSCRIPT"}
    assert len(plan["EARNINGS_CALL_TRANSCRIPT"]) == 1

    results = orchestrator.dispatch()

    assert len(results) == 1
    assert results[0].status == "ok"
    assert client.calls[0]["symbol"] == "NVDA"
    assert client.calls[0]["quarter"] == "2024Q3"
    assert client.calls[0]["function"] == "EARNINGS_CALL_TRANSCRIPT"


def test_orchestrator_requires_api_key() -> None:
    settings = build_settings()

    with pytest.raises(RuntimeError, match="API key"):
        AlphaVantageOrchestrator(settings=settings, env={}, persist_results=False)


def test_missing_context_keys_raise_before_dispatch() -> None:
    settings = build_settings()
    settings["ingestion"]["alpha_vantage"]["endpoints"]["EARNINGS_CALL_TRANSCRIPT"]["contexts"] = [
        {"symbol": "NVDA"},
    ]

    client = FakeAlphaVantageClient([
        {"data": {}},
    ])

    orchestrator = AlphaVantageOrchestrator(
        settings=settings,
        env={"ALPHAVANTAGE_API_KEY": "dummy"},
        client=client,
        persist_results=False,
    )

    with pytest.raises(ValueError, match="missing keys"):
        orchestrator.build_job_plan()


def test_replace_defaults_allows_slimming_contexts() -> None:
    settings = build_settings()
    settings["ingestion"]["alpha_vantage"]["enabled_endpoints"] = ["MACD"]
    settings["ingestion"]["alpha_vantage"]["endpoints"]["MACD"] = {
        "contexts": [{"symbol": "NVDA"}],
        "replace_defaults": True,
    }

    client = FakeAlphaVantageClient([
        {"data": {}},
    ])

    orchestrator = AlphaVantageOrchestrator(
        settings=settings,
        env={"ALPHAVANTAGE_API_KEY": "dummy"},
        client=client,
        persist_results=False,
    )

    plan = orchestrator.build_job_plan()
    assert set(plan) == {"MACD"}
    assert len(plan["MACD"]) == 1


def test_dispatch_persists_results_to_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build_settings()
    settings["ingestion"]["alpha_vantage"] = {
        "enabled_endpoints": ["NEWS_SENTIMENT"],
        "endpoints": {
            "NEWS_SENTIMENT": {
                "contexts": [{"symbol": "NVDA"}],
                "replace_defaults": True,
            }
        },
    }
    settings["services"]["redis"] = {
        "url_env": "REDIS_URL",
        "default_ttl_seconds": 120,
        "min_ttl_seconds": 60,
        "max_ttl_seconds": 600,
    }

    fake_env = {
        "ALPHAVANTAGE_API_KEY": "test-key",
        "REDIS_URL": "redis://unused",
    }
    client = FakeAlphaVantageClient([
        {"data": {"value": 1}},
    ])
    fake_redis = FakeRedis()

    orchestrator = AlphaVantageOrchestrator(
        settings=settings,
        env=fake_env,
        client=client,
        redis_client=fake_redis,
        persist_results=True,
    )

    results = orchestrator.dispatch()

    assert len(results) == 1
    key = "raw:alpha_vantage:news_sentiment:NVDA"
    assert key in fake_redis.storage
    stored = fake_redis.storage[key]
    payload = json.loads(stored["value"])
    assert stored["ttl"] == 600
    assert payload["ttl_applied"] == 600

    metrics = orchestrator.metrics_snapshot()
    assert metrics["total"] == 1
    assert metrics["ok"] == 1
    assert metrics.get("ttl_clamped_high") == 1


def test_persist_result_clamps_low_ttl() -> None:
    settings = build_settings()
    settings["services"]["redis"] = {
        "url_env": "REDIS_URL",
        "default_ttl_seconds": 600,
        "min_ttl_seconds": 300,
        "max_ttl_seconds": 3600,
    }

    fake_env = {"ALPHAVANTAGE_API_KEY": "test"}
    client = FakeAlphaVantageClient([{}])
    fake_redis = FakeRedis()

    orchestrator = AlphaVantageOrchestrator(
        settings=settings,
        env=fake_env,
        client=client,
        redis_client=fake_redis,
        persist_results=True,
    )

    job_name = "alpha_vantage.test" 
    redis_key = "raw:alpha_vantage:test:clamp"
    result = RunnerResult(
        job_name=job_name,
        status="ok",
        attempts=1,
        started_at=0.0,
        finished_at=0.1,
        payload={
            "redis_key": redis_key,
            "ttl_applied": None,
            "data": {"sample": True},
        },
        error=None,
        metadata={
            "redis_key": redis_key,
            "ttl_seconds": 120,
        },
    )

    orchestrator._persist_result(result)

    stored = fake_redis.storage[redis_key]
    payload = json.loads(stored["value"])
    assert stored["ttl"] == 300  # clamped to min TTL
    assert payload["ttl_applied"] == 300
    assert orchestrator.metrics_snapshot()["ttl_clamped_low"] == 1
