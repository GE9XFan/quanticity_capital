"""Unit tests for the shared ingestion runner skeleton."""

from __future__ import annotations

from typing import Callable, List

import pytest

from quanticity_capital import (
    IngestionJob,
    RateLimiter,
    RetryPolicy,
    Runner,
)


class FakeClock:
    """Deterministic wall-clock for runner tests."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def build_sleep(clock: FakeClock, bucket: List[float]) -> Callable[[float], None]:
    def _sleep(seconds: float) -> None:
        bucket.append(seconds)
        clock.advance(seconds)

    return _sleep


def test_runner_successful_job() -> None:
    clock = FakeClock()
    sleeps: List[float] = []
    runner = Runner(clock=clock, sleeper=build_sleep(clock, sleeps))

    job = IngestionJob(name="simple", operation=lambda attempt: {"attempt": attempt})

    result = runner.run(job)

    assert result.status == "ok"
    assert result.payload == {"attempt": 1}
    assert result.attempts == 1
    assert sleeps == []


def test_runner_retries_on_retryable_exception() -> None:
    clock = FakeClock()
    sleeps: List[float] = []
    runner = Runner(clock=clock, sleeper=build_sleep(clock, sleeps))

    attempts: List[int] = []

    def operation(attempt: int) -> str:
        attempts.append(attempt)
        if attempt == 1:
            raise ValueError("transient")
        return "payload"

    policy = RetryPolicy(
        max_attempts=3,
        backoff_seconds=(2.5,),
        retry_exceptions=(ValueError,),
    )

    job = IngestionJob(
        name="retryable",
        operation=operation,
        retry_policy=policy,
    )

    result = runner.run(job)

    assert result.status == "ok"
    assert result.attempts == 2
    assert attempts == [1, 2]
    assert pytest.approx(result.duration, abs=1e-9) == 2.5
    assert sleeps == [2.5]


def test_runner_stops_on_non_retryable_exception() -> None:
    clock = FakeClock()
    runner = Runner(clock=clock, sleeper=build_sleep(clock, []))

    def operation(_: int) -> None:
        raise RuntimeError("boom")

    job = IngestionJob(
        name="non-retryable",
        operation=operation,
        retry_policy=RetryPolicy(
            max_attempts=3,
            retry_exceptions=(ValueError,),
        ),
    )

    result = runner.run(job)

    assert result.status == "error"
    assert isinstance(result.error, RuntimeError)
    assert result.attempts == 1


def test_runner_obeys_registered_rate_limiter() -> None:
    clock = FakeClock()
    sleeps: List[float] = []
    runner = Runner(clock=clock, sleeper=build_sleep(clock, sleeps))
    runner.register_rate_limiter("alpha_vantage", RateLimiter(max_calls=1, period=5.0, clock=clock))

    job = IngestionJob(
        name="rate-limited",
        operation=lambda attempt: attempt,
        rate_limit_key="alpha_vantage",
    )

    first = runner.run(job)
    second = runner.run(job)

    assert first.status == "ok"
    assert second.status == "ok"
    assert sleeps == [5.0]
    assert second.attempts == 1
    assert pytest.approx(second.duration, abs=1e-9) == 5.0


def test_runner_has_rate_limiter() -> None:
    clock = FakeClock()
    runner = Runner(clock=clock, sleeper=build_sleep(clock, []))

    assert runner.has_rate_limiter("alpha_vantage") is False

    runner.register_rate_limiter("alpha_vantage", RateLimiter(max_calls=1, period=1.0, clock=clock))

    assert runner.has_rate_limiter("alpha_vantage") is True
