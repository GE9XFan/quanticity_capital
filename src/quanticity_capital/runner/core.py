"""Shared ingestion runner components for Phase 2 Alpha Vantage work."""

from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, Literal, Optional, Sequence


@dataclass(frozen=True)
class RetryPolicy:
    """Defines retry behaviour for ingestion jobs."""

    max_attempts: int = 3
    backoff_seconds: Sequence[float] = (1.0, 3.0, 7.0)
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,)
    jitter_range: Optional[tuple[float, float]] = None

    def should_retry(self, exc: BaseException, attempt_number: int) -> bool:
        """Return True when the exception is retryable and attempts remain."""

        if attempt_number >= self.max_attempts:
            return False
        return isinstance(exc, self.retry_exceptions)

    def compute_backoff(self, attempt_number: int, rng: random.Random) -> float:
        """Return the backoff delay (with optional jitter) for a retry."""

        if not self.backoff_seconds:
            base = 0.0
        else:
            index = min(max(attempt_number - 1, 0), len(self.backoff_seconds) - 1)
            base = float(self.backoff_seconds[index])

        if self.jitter_range is None:
            return base

        jitter_low, jitter_high = self.jitter_range
        return base + rng.uniform(jitter_low, jitter_high)


class RateLimiter:
    """Simple sliding-window rate limiter."""

    __slots__ = ("_max_calls", "_period", "_clock", "_timestamps")

    def __init__(
        self,
        max_calls: int,
        period: float,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls must be positive")
        if period <= 0:
            raise ValueError("period must be positive")

        self._max_calls = max_calls
        self._period = float(period)
        self._clock = clock or time.monotonic
        self._timestamps: Deque[float] = deque()

    def reserve(self) -> float:
        """Return delay required before the next call is permitted."""

        while True:
            now = self._clock()
            self._trim_expired(now)
            if len(self._timestamps) < self._max_calls:
                self._timestamps.append(now)
                return 0.0

            earliest = self._timestamps[0]
            wait = (earliest + self._period) - now
            if wait <= 0:
                self._timestamps.popleft()
                continue
            return wait

    def _trim_expired(self, now: float) -> None:
        threshold = now - self._period
        while self._timestamps and self._timestamps[0] <= threshold:
            self._timestamps.popleft()


@dataclass
class IngestionJob:
    """Represents a single ingestion attempt for a specific endpoint."""

    name: str
    operation: Callable[[int], Any]
    rate_limit_key: Optional[str] = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunnerResult:
    """Outcome of executing an ingestion job."""

    job_name: str
    status: Literal["ok", "error"]
    attempts: int
    started_at: float
    finished_at: float
    payload: Any = None
    error: Optional[BaseException] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.finished_at - self.started_at


class Runner:
    """Executes ingestion jobs with shared retry/backoff and rate limits."""

    def __init__(
        self,
        *,
        rate_limiters: Optional[Dict[str, RateLimiter]] = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._rate_limiters: Dict[str, RateLimiter] = dict(rate_limiters or {})
        self._clock = clock or time.monotonic
        self._sleep = sleeper or time.sleep
        self._rng = rng or random.Random()

    def register_rate_limiters(self, items: Iterable[tuple[str, RateLimiter]]) -> None:
        for key, limiter in items:
            self._rate_limiters[key] = limiter

    def register_rate_limiter(self, key: str, limiter: RateLimiter) -> None:
        self._rate_limiters[key] = limiter

    def has_rate_limiter(self, key: str) -> bool:
        """Return True when a rate limiter with the given key is registered."""

        return key in self._rate_limiters

    def run(self, job: IngestionJob) -> RunnerResult:
        attempts = 0
        started_at = self._clock()
        last_error: Optional[BaseException] = None
        payload: Any = None

        while True:
            attempts += 1
            self._respect_rate_limit(job.rate_limit_key)
            try:
                payload = job.operation(attempts)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not job.retry_policy.should_retry(exc, attempts):
                    finished_at = self._clock()
                    return RunnerResult(
                        job_name=job.name,
                        status="error",
                        attempts=attempts,
                        started_at=started_at,
                        finished_at=finished_at,
                        payload=None,
                        error=exc,
                        metadata=dict(job.metadata),
                    )

                delay = job.retry_policy.compute_backoff(attempts, self._rng)
                if delay > 0:
                    self._sleep(delay)
                continue

            finished_at = self._clock()
            return RunnerResult(
                job_name=job.name,
                status="ok",
                attempts=attempts,
                started_at=started_at,
                finished_at=finished_at,
                payload=payload,
                error=None,
                metadata=dict(job.metadata),
            )

    def _respect_rate_limit(self, key: Optional[str]) -> None:
        if key is None:
            return
        limiter = self._rate_limiters.get(key)
        if limiter is None:
            raise KeyError(f"Rate limiter '{key}' is not registered")

        while True:
            delay = limiter.reserve()
            if delay <= 0:
                return
            self._sleep(delay)


__all__ = [
    "IngestionJob",
    "RateLimiter",
    "RetryPolicy",
    "Runner",
    "RunnerResult",
]
