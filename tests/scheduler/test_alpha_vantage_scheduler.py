"""Tests for the Alpha Vantage scheduler."""

from __future__ import annotations

from datetime import datetime, time as dt_time
from typing import Mapping, Sequence

from zoneinfo import ZoneInfo

import pytest

from quanticity_capital.runner import IngestionJob, RunnerResult
from quanticity_capital.scheduler import AlphaVantageScheduler


class StubRedis:
    """Redis stub that exposes ttl lookups for guard testing."""

    def __init__(self, ttl_map: Mapping[str, int]) -> None:
        self._ttl_map = dict(ttl_map)

    def ttl(self, key: str) -> int:
        return int(self._ttl_map.get(key, -2))


class StubOrchestrator:
    """Minimal orchestrator stub compatible with the scheduler contract."""

    def __init__(self, plan: Mapping[str, Sequence[IngestionJob]], redis_client: StubRedis) -> None:
        self._plan = plan
        self._redis = redis_client
        self.dispatch_calls: list[Mapping[str, Sequence[IngestionJob]]] = []

    def build_job_plan(self) -> Mapping[str, Sequence[IngestionJob]]:
        return self._plan

    def dispatch(self, plan: Mapping[str, Sequence[IngestionJob]]) -> Sequence[RunnerResult]:
        self.dispatch_calls.append(plan)
        job = next(iter(plan.values()))[0]
        return [
            RunnerResult(
                job_name=job.name,
                status="ok",
                attempts=1,
                started_at=0.0,
                finished_at=0.1,
                payload={},
                error=None,
                metadata=dict(job.metadata),
            )
        ]

    def redis_client(self) -> StubRedis:
        return self._redis


@pytest.fixture()
def simple_job() -> IngestionJob:
    return IngestionJob(
        name="alpha_vantage.test",
        operation=lambda attempt: {},
        metadata={"redis_key": "raw:alpha_vantage:test", "ttl_seconds": 300},
    )


def test_scheduler_skips_jobs_when_ttl_guard_active(simple_job: IngestionJob) -> None:
    redis = StubRedis({"raw:alpha_vantage:test": 900})
    plan = {"TEST": (simple_job,)}
    orchestrator = StubOrchestrator(plan, redis)

    scheduler = AlphaVantageScheduler(
        orchestrator,
        poll_interval=60,
        refresh_guard_seconds=120,
    )

    now = datetime(2025, 10, 1, 14, 0, tzinfo=ZoneInfo("America/New_York"))
    results = scheduler.run_cycle(now=now)

    assert results == ()
    assert not orchestrator.dispatch_calls


def test_scheduler_dispatches_jobs_when_ttl_near_expiry(simple_job: IngestionJob) -> None:
    redis = StubRedis({"raw:alpha_vantage:test": 30})
    plan = {"TEST": (simple_job,)}
    orchestrator = StubOrchestrator(plan, redis)

    scheduler = AlphaVantageScheduler(
        orchestrator,
        poll_interval=60,
        refresh_guard_seconds=120,
    )

    now = datetime(2025, 10, 1, 14, 0, tzinfo=ZoneInfo("America/New_York"))
    results = scheduler.run_cycle(now=now)

    assert len(results) == 1
    assert len(orchestrator.dispatch_calls) == 1


def test_scheduler_skips_outside_trading_hours(simple_job: IngestionJob) -> None:
    redis = StubRedis({})
    plan = {"TEST": (simple_job,)}
    orchestrator = StubOrchestrator(plan, redis)

    scheduler = AlphaVantageScheduler(
        orchestrator,
        poll_interval=60,
        refresh_guard_seconds=120,
        trading_open=dt_time(9, 30),
        trading_close=dt_time(16, 0),
    )

    # Sunday evening outside trading hours.
    now = datetime(2025, 9, 28, 20, 0, tzinfo=ZoneInfo("America/New_York"))
    results = scheduler.run_cycle(now=now)

    assert results == ()
    assert not orchestrator.dispatch_calls
