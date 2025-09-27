"""Unit tests for the Alpha Vantage connector."""

from __future__ import annotations

from collections import deque
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

import pytest

from quanticity_capital.ingestion import (
    ALPHA_VANTAGE_ENDPOINT_SPECS,
    DEFAULT_ALPHA_VANTAGE_CONTEXTS,
    AlphaVantageConnector,
    AlphaVantageInvalidRequestError,
    AlphaVantageRetryableError,
    AlphaVantageThrottleError,
)
from quanticity_capital.runner import Runner


class FakeClock:
    """Deterministic clock mirroring the runner tests."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def build_sleep(clock: FakeClock, bucket: list[float]) -> Callable[[float], None]:
    def _sleep(seconds: float) -> None:
        bucket.append(seconds)
        clock.advance(seconds)

    return _sleep


class FakeAlphaVantageClient:
    """Fake client that dequeues pre-seeded responses and records calls."""

    def __init__(self, responses: Iterable[Any]) -> None:
        self._responses = deque(responses)
        self.calls: list[Dict[str, Any]] = []

    def fetch(self, params: Mapping[str, Any]) -> Any:
        self.calls.append(dict(params))
        if not self._responses:
            raise AssertionError("unexpected Alpha Vantage call")
        payload = self._responses.popleft()
        if isinstance(payload, Exception):
            raise payload
        return payload


@pytest.mark.parametrize("endpoint", ["REALTIME_OPTIONS", "TIME_SERIES_INTRADAY"])
def test_build_job_and_run_successfully(endpoint: str) -> None:
    clock = FakeClock()
    sleeps: list[float] = []
    runner = Runner(clock=clock, sleeper=build_sleep(clock, sleeps))

    client = FakeAlphaVantageClient([
        {"sample": "data", "endpoint": endpoint.lower()},
    ])

    connector = AlphaVantageConnector(runner, client, clock=clock)

    spec = ALPHA_VANTAGE_ENDPOINT_SPECS[endpoint]
    context = {"symbol": "AAPL"}

    result = connector.run(endpoint, context)

    assert result.status == "ok"
    assert result.attempts == 1
    assert result.metadata["endpoint"] == spec.endpoint
    assert result.metadata["redis_key"] == spec.redis_key_template.format(**context)
    assert result.payload["request_params"]["function"] == spec.static_params["function"]
    assert result.payload["context"] == context
    assert client.calls[0]["symbol" if "symbol" in client.calls[0] else "tickers"] == "AAPL"


def test_throttle_response_retries_and_succeeds() -> None:
    clock = FakeClock()
    sleeps: list[float] = []
    runner = Runner(clock=clock, sleeper=build_sleep(clock, sleeps))

    client = FakeAlphaVantageClient([
        {"Note": "Please slow down"},
        {"data": "ok"},
    ])

    connector = AlphaVantageConnector(runner, client, clock=clock)

    result = connector.run("VWAP", {"symbol": "NVDA"})

    assert result.status == "ok"
    assert result.attempts == 2
    assert isinstance(result.payload["data"], dict)
    assert len(client.calls) == 2
    assert sleeps  # backoff applied via RetryPolicy defaults


def test_error_message_halts_without_retry() -> None:
    clock = FakeClock()
    runner = Runner(clock=clock, sleeper=build_sleep(clock, []))
    client = FakeAlphaVantageClient([
        {"Error Message": "Invalid API call"},
    ])

    connector = AlphaVantageConnector(runner, client, clock=clock)

    result = connector.run("MACD", {"symbol": "TSLA"})

    assert result.status == "error"
    assert isinstance(result.error, AlphaVantageInvalidRequestError)
    assert result.attempts == 1


def test_default_contexts_news_sentiment_excludes_etfs() -> None:
    connector = AlphaVantageConnector(Runner(), FakeAlphaVantageClient([{}]), auto_register_rate_limiters=False)

    contexts = connector.default_contexts("NEWS_SENTIMENT")
    symbols: Sequence[str] = [context["symbol"] for context in contexts]

    assert "SPY" not in symbols
    assert "QQQ" not in symbols
    assert "IWM" not in symbols
    assert symbols  # still populated with equities


def test_rate_limiters_register_once() -> None:
    clock = FakeClock()
    runner = Runner(clock=clock, sleeper=build_sleep(clock, []))
    client = FakeAlphaVantageClient([{}])

    connector = AlphaVantageConnector(runner, client, clock=clock)

    for key in (
        "alpha_vantage:core",
        "alpha_vantage:news",
        "alpha_vantage:macro",
        "alpha_vantage:fundamentals",
    ):
        assert runner.has_rate_limiter(key)

    # Invoking again should not create duplicate limiters nor raise.
    connector.ensure_rate_limiters()


def test_macro_job_captures_metadata_and_payload() -> None:
    clock = FakeClock()
    runner = Runner(clock=clock, sleeper=build_sleep(clock, []))
    client = FakeAlphaVantageClient([
        {"data": [1, 2, 3]},
    ])

    connector = AlphaVantageConnector(runner, client, clock=clock)

    result = connector.run("REAL_GDP", {"interval": "quarterly"})

    assert result.status == "ok"
    assert result.metadata["redis_key"] == "raw:alpha_vantage:macro:real_gdp:quarterly"
    assert result.payload["context"] == {"interval": "quarterly"}
    assert result.payload["endpoint"] == "REAL_GDP"


def test_default_context_registry_matches_spec_keys() -> None:
    # Ensure we keep context helpers in sync with endpoint registry for future maintenance.
    diff = set(DEFAULT_ALPHA_VANTAGE_CONTEXTS) ^ set(ALPHA_VANTAGE_ENDPOINT_SPECS)
    assert not diff, f"Context registry mismatch: {diff}"


def test_throttle_exception_subclass() -> None:
    error = AlphaVantageThrottleError("throttled")
    assert isinstance(error, AlphaVantageThrottleError)
    assert isinstance(error, AlphaVantageRetryableError)


def test_spec_for_returns_endpoint_spec() -> None:
    connector = AlphaVantageConnector(
        Runner(),
        FakeAlphaVantageClient([{}]),
        auto_register_rate_limiters=False,
    )

    spec = connector.spec_for("MACD")

    assert spec.endpoint == "MACD"
    assert spec.entity == "macd"
