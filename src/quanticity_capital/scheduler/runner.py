"""Scheduler runtime coordination."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

import structlog

from ..config.models import ScheduleConfig
from ..core.redis import RetryConfig, redis_retry
from .jobs import RotationQueue, ScheduledJob
from .rate_limits import TokenBucket
from .state import load_scheduler_state, persist_scheduler_state, restore_from_state


@dataclass(slots=True)
class SchedulerSnapshot:
    jobs: Dict[str, datetime]
    buckets: Dict[str, float]
    rotations: Dict[str, list[str]]


class Scheduler:
    """Token-bucket aware scheduler that dispatches Redis stream events."""

    def __init__(
        self,
        *,
        config: ScheduleConfig,
        redis,
        heartbeat_ttl: int,
        logger: Optional[structlog.stdlib.BoundLogger] = None,
    ) -> None:
        self.config = config
        self.redis = redis
        self.heartbeat_ttl = max(heartbeat_ttl, 1)
        self.logger = logger or structlog.get_logger("scheduler")
        self._stop_event = asyncio.Event()
        self._task_group: Optional[asyncio.TaskGroup] = None
        self._buckets: Dict[str, TokenBucket] = {
            name: TokenBucket(name, bucket_cfg) for name, bucket_cfg in config.buckets.items()
        }
        self._jobs: Dict[str, ScheduledJob] = {
            name: ScheduledJob(name, job_cfg) for name, job_cfg in config.jobs.items()
        }
        self._rotations: Dict[str, list[str]] = {}
        self._retry_config = RetryConfig()
        self._state_lock = asyncio.Lock()

    async def start(self) -> None:
        if self._task_group is not None:
            raise RuntimeError("Scheduler already running")
        await self._restore_state()
        async with asyncio.TaskGroup() as tg:
            self._task_group = tg
            tg.create_task(self._heartbeat_loop(), name="scheduler-heartbeat")
            tg.create_task(self._dispatch_loop(), name="scheduler-dispatch")
            tg.create_task(self._state_loop(), name="scheduler-state")
        self._task_group = None

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task_group is not None:
            await asyncio.sleep(0)

    def register_rotation(self, job_id: str, values: Iterable[str]) -> None:
        if job_id not in self._jobs:
            raise KeyError(f"Unknown job '{job_id}'")
        queue = RotationQueue.from_iterable(job_id, values)
        self._jobs[job_id].attach_rotation(queue)
        self._rotations[job_id] = list(values)

    def snapshot(self) -> SchedulerSnapshot:
        jobs = {name: job.next_run for name, job in self._jobs.items()}
        buckets = {name: bucket.tokens for name, bucket in self._buckets.items()}
        rotations = {name: list(items) for name, items in self._rotations.items()}
        return SchedulerSnapshot(jobs=jobs, buckets=buckets, rotations=rotations)

    async def _restore_state(self) -> None:
        state = await load_scheduler_state(self.redis)
        restore_from_state(
            state=state, jobs=self._jobs, buckets=self._buckets, rotations=self._rotations
        )
        for name, items in self._rotations.items():
            if name in self._jobs and items:
                self._jobs[name].attach_rotation(RotationQueue.from_iterable(name, items))

    async def _heartbeat_loop(self) -> None:
        key = "system:heartbeat:scheduler"
        while not self._stop_event.is_set():
            now = datetime.now(tz=timezone.utc).isoformat()
            await self.redis.set(key, now, ex=self.heartbeat_ttl)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=max(self.heartbeat_ttl / 2, 1)
                )
            except asyncio.TimeoutError:
                continue
        await self.redis.set(key, datetime.now(tz=timezone.utc).isoformat(), ex=self.heartbeat_ttl)

    async def _dispatch_loop(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now(tz=timezone.utc)
            due_jobs = [job for job in self._jobs.values() if job.due(now)]
            for job in due_jobs:
                await self._maybe_dispatch(job, now)
            sleep_for = self._next_sleep_interval(now)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                continue
        # flush outstanding state on shutdown
        await self._flush_state()

    async def _maybe_dispatch(self, job: ScheduledJob, now: datetime) -> None:
        bucket_name = job.config.bucket
        if bucket_name:
            bucket = self._buckets.get(bucket_name)
            if bucket is None:
                self.logger.warning("Bucket missing for job", job=job.job_id, bucket=bucket_name)
                return
            if not bucket.consume(now=now.timestamp()):
                return
        rotation_value = job.consume_rotation()
        await self._publish_job(job, now, rotation_value)
        job.mark_dispatched(now)
        key = f"system:schedule:last_run:{job.job_id}"
        await self.redis.set(key, now.isoformat(), ex=self.heartbeat_ttl)

    async def _publish_job(
        self,
        job: ScheduledJob,
        dispatched_at: datetime,
        rotation_value: Optional[str],
    ) -> None:
        payload = {
            "job": job.job_id,
            "scheduled_for": job.next_run.isoformat(),
            "dispatched_at": dispatched_at.isoformat(),
        }
        if rotation_value is not None:
            payload["rotation"] = rotation_value
        stream = f"stream:schedule:{job.job_id}"

        async def _xadd():
            return await self.redis.xadd(stream, payload)  # type: ignore[arg-type]

        await redis_retry(_xadd, retry_config=self._retry_config, logger=self.logger)

    def _next_sleep_interval(self, now: datetime) -> float:
        upcoming = [max((job.next_run - now).total_seconds(), 0.1) for job in self._jobs.values()]
        if not upcoming:
            return 1.0
        return min(upcoming)

    async def _state_loop(self) -> None:
        while not self._stop_event.is_set():
            await self._flush_state()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                continue

    async def _flush_state(self) -> None:
        async with self._state_lock:
            rotations_snapshot: Dict[str, list[str]] = {}
            for job_id, job in self._jobs.items():
                if job._rotation is not None:
                    rotations_snapshot[job_id] = list(job._rotation.values)
                else:
                    rotations_snapshot[job_id] = list(self._rotations.get(job_id, []))
            await persist_scheduler_state(
                self.redis,
                jobs=self._jobs,
                buckets=self._buckets,
                rotations=rotations_snapshot,
            )


__all__ = ["Scheduler", "SchedulerSnapshot"]
