"""Scheduler job definitions and rotation queues."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Iterable, Optional

from croniter import croniter  # type: ignore[import-not-found,import-untyped]

from ..config.models import ScheduleJobConfig


@dataclass(slots=True)
class RotationQueue:
    """Simple rotation queue used for symbol cycling."""

    name: str
    values: Deque[str] = field(default_factory=deque)

    @classmethod
    def from_iterable(cls, name: str, items: Iterable[str]) -> "RotationQueue":
        return cls(name=name, values=deque(items))

    def next(self) -> Optional[str]:
        if not self.values:
            return None
        value = self.values.popleft()
        self.values.append(value)
        return value

    def snapshot(self) -> Dict[str, list[str]]:
        return {self.name: list(self.values)}

    def restore(self, data: Iterable[str]) -> None:
        self.values = deque(data)


@dataclass(slots=True)
class JobState:
    next_run: str


class ScheduledJob:
    """Wrap cron configuration and runtime state."""

    def __init__(self, job_id: str, config: ScheduleJobConfig) -> None:
        self.job_id = job_id
        self.config = config
        self._rotation: Optional[RotationQueue] = None
        now = datetime.now(tz=timezone.utc)
        self._cron = croniter(config.cadence, now)
        self.next_run = self._compute_next(now)
        self.last_run: Optional[datetime] = None

    def attach_rotation(self, rotation: RotationQueue) -> None:
        self._rotation = rotation

    def _compute_next(self, base: datetime) -> datetime:
        candidate = self._cron.get_next(datetime)
        jitter = self.config.jitter_seconds
        if jitter:
            offset = random.uniform(-jitter, jitter)
            candidate = candidate + timedelta(seconds=offset)
        if candidate < base:
            return base
        return candidate

    def due(self, now: datetime) -> bool:
        return now >= self.next_run

    def consume_rotation(self) -> Optional[str]:
        if self._rotation is None:
            return None
        return self._rotation.next()

    def mark_dispatched(self, now: datetime) -> None:
        self.last_run = now
        self.next_run = self._compute_next(now)

    def snapshot(self) -> JobState:
        return JobState(next_run=self.next_run.isoformat())

    def restore(self, state: JobState) -> None:
        try:
            self.next_run = datetime.fromisoformat(state.next_run)
        except ValueError:  # pragma: no cover - resilience
            self.next_run = datetime.now(tz=timezone.utc)


def snapshot_jobs(jobs: Dict[str, ScheduledJob]) -> Dict[str, JobState]:
    return {name: job.snapshot() for name, job in jobs.items()}


def restore_jobs(jobs: Dict[str, ScheduledJob], state: Dict[str, JobState]) -> None:
    for name, job in jobs.items():
        if name in state:
            job.restore(state[name])


__all__ = [
    "JobState",
    "RotationQueue",
    "ScheduledJob",
    "restore_jobs",
    "snapshot_jobs",
]
