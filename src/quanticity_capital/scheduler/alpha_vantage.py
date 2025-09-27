"""Trading-hours aware scheduler for the Alpha Vantage orchestrator."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, time as dt_time, timedelta
from typing import Dict, Mapping, Sequence

import structlog
from redis import Redis
from zoneinfo import ZoneInfo

from quanticity_capital.orchestrator import AlphaVantageOrchestrator
from quanticity_capital.runner import IngestionJob, RunnerResult


class AlphaVantageScheduler:
    """Run Alpha Vantage ingestion loops during US trading hours."""

    def __init__(
        self,
        orchestrator: AlphaVantageOrchestrator,
        *,
        poll_interval: float = 60.0,
        refresh_guard_seconds: int = 120,
        trading_timezone: str = "America/New_York",
        trading_open: dt_time = dt_time(9, 30),
        trading_close: dt_time = dt_time(16, 0),
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        if refresh_guard_seconds < 0:
            raise ValueError("refresh_guard_seconds cannot be negative")

        self._orchestrator = orchestrator
        self._poll_interval = float(poll_interval)
        self._refresh_guard_seconds = int(refresh_guard_seconds)
        self._logger = structlog.get_logger("quanticity_capital.scheduler.alpha_vantage")
        self._tz = ZoneInfo(trading_timezone)
        self._trading_open = trading_open
        self._trading_close = trading_close

        self._redis: Redis | None = orchestrator.redis_client()
        if self._redis is None:
            raise RuntimeError(
                "AlphaVantageScheduler requires orchestrator persistence to be enabled"
            )

    def run_forever(self) -> None:
        """Start the scheduler loop until interrupted."""

        while True:
            now = datetime.now(self._tz)
            results = self.run_cycle(now=now)

            if not self.within_trading_hours(now):
                sleep_for = min(self._seconds_until_open(now), 900.0)
            elif results:
                sleep_for = self._poll_interval
            else:
                sleep_for = self._poll_interval

            time.sleep(max(sleep_for, 1.0))

    def run_cycle(self, *, now: datetime | None = None) -> Sequence[RunnerResult]:
        """Execute a single scheduling decision."""

        now = now or datetime.now(self._tz)
        if not self.within_trading_hours(now):
            self._logger.info(
                "scheduler.skip_outside_hours",
                timestamp=now.isoformat(),
            )
            return ()

        plan = self._orchestrator.build_job_plan()
        filtered_plan, skipped_breakdown = self._filter_plan(plan)

        if not filtered_plan:
            skipped_total = sum(skipped_breakdown.values())
            self._logger.info(
                "scheduler.ttl_guard_skip",
                skipped_total=skipped_total,
                skipped_by_endpoint=dict(skipped_breakdown),
            )
            return ()

        dispatched = sum(len(jobs) for jobs in filtered_plan.values())
        self._logger.info(
            "scheduler.dispatching",
            endpoints=len(filtered_plan),
            jobs=dispatched,
        )
        results = self._orchestrator.dispatch(filtered_plan)
        return results

    def within_trading_hours(self, now: datetime | None = None) -> bool:
        """Return True when the provided time falls inside trading hours."""

        now = now or datetime.now(self._tz)
        if now.weekday() >= 5:  # Saturday/Sunday
            return False
        current = now.time()
        return self._trading_open <= current < self._trading_close

    def _filter_plan(
        self,
        plan: Mapping[str, Sequence[IngestionJob]],
    ) -> tuple[Dict[str, Sequence[IngestionJob]], Dict[str, int]]:
        redis_client = self._redis
        if redis_client is None:
            return dict(plan), defaultdict(int)

        filtered: Dict[str, list[IngestionJob]] = {}
        skipped: Dict[str, int] = defaultdict(int)

        for endpoint, jobs in plan.items():
            for job in jobs:
                if self._should_run_job(redis_client, job):
                    filtered.setdefault(endpoint, []).append(job)
                else:
                    skipped[endpoint] += 1

        normalized = {endpoint: tuple(jobs) for endpoint, jobs in filtered.items()}
        return normalized, dict(skipped)

    def _should_run_job(self, redis_client: Redis, job: IngestionJob) -> bool:
        if self._refresh_guard_seconds == 0:
            return True

        redis_key = job.metadata.get("redis_key")
        if not isinstance(redis_key, str) or not redis_key:
            return True

        try:
            ttl = redis_client.ttl(redis_key)
        except Exception:  # pragma: no cover - defensive guard for redis errors
            self._logger.warning(
                "scheduler.ttl_lookup_failed",
                redis_key=redis_key,
                exc_info=True,
            )
            return True

        if ttl is None or ttl < 0:
            return True

        guard = self._refresh_guard_seconds
        ttl_setting = job.metadata.get("ttl_seconds")
        if isinstance(ttl_setting, int) and ttl_setting > 0:
            guard = min(guard, ttl_setting)

        if ttl > guard:
            self._logger.debug(
                "scheduler.ttl_guard_active",
                redis_key=redis_key,
                ttl=ttl,
                guard=guard,
            )
            return False
        return True

    def _seconds_until_open(self, now: datetime) -> float:
        current_date = now.date()
        target_date = current_date

        if now.time() >= self._trading_close:
            target_date += timedelta(days=1)

        while datetime.combine(target_date, dt_time(0, 0), tzinfo=self._tz).weekday() >= 5:
            target_date += timedelta(days=1)

        next_open = datetime.combine(target_date, self._trading_open, tzinfo=self._tz)
        delta = (next_open - now).total_seconds()
        if delta <= 0:
            return self._poll_interval
        return max(delta, self._poll_interval)