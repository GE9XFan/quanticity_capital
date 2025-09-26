"""Persistence helpers for scheduler state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict

from ..core import fetch_json, write_json
from .jobs import JobState, ScheduledJob, restore_jobs, snapshot_jobs
from .rate_limits import TokenBucket, TokenBucketState, restore_buckets, snapshot_buckets

JOB_STATE_KEY = "state:scheduler:jobs"
BUCKET_STATE_KEY = "state:scheduler:buckets"
ROTATION_STATE_KEY = "state:scheduler:rotations"


@dataclass(slots=True)
class SchedulerState:
    jobs: Dict[str, JobState]
    buckets: Dict[str, TokenBucketState]
    rotations: Dict[str, list[str]]


async def load_scheduler_state(redis) -> SchedulerState:
    jobs_payload = await fetch_json(redis, JOB_STATE_KEY, default={}) or {}
    bucket_payload = await fetch_json(redis, BUCKET_STATE_KEY, default={}) or {}
    rotations_payload = await fetch_json(redis, ROTATION_STATE_KEY, default={}) or {}

    jobs_state = {name: JobState(**data) for name, data in jobs_payload.items()}
    bucket_state = {name: TokenBucketState(**data) for name, data in bucket_payload.items()}
    rotations_state = {name: list(values) for name, values in rotations_payload.items()}
    return SchedulerState(jobs=jobs_state, buckets=bucket_state, rotations=rotations_state)


async def persist_scheduler_state(
    redis,
    *,
    jobs: Dict[str, ScheduledJob],
    buckets: Dict[str, TokenBucket],
    rotations: Dict[str, list[str]],
) -> None:
    job_state = {name: asdict(state) for name, state in snapshot_jobs(jobs).items()}
    bucket_state = {name: asdict(state) for name, state in snapshot_buckets(buckets).items()}
    await write_json(redis, JOB_STATE_KEY, job_state)
    await write_json(redis, BUCKET_STATE_KEY, bucket_state)
    await write_json(redis, ROTATION_STATE_KEY, rotations)


def restore_from_state(
    *,
    state: SchedulerState,
    jobs: Dict[str, ScheduledJob],
    buckets: Dict[str, TokenBucket],
    rotations: Dict[str, list[str]],
) -> None:
    restore_jobs(jobs, state.jobs)
    restore_buckets(buckets, state.buckets)
    for name, items in state.rotations.items():
        rotations[name] = items


__all__ = [
    "SchedulerState",
    "load_scheduler_state",
    "persist_scheduler_state",
    "restore_from_state",
    "JOB_STATE_KEY",
    "BUCKET_STATE_KEY",
    "ROTATION_STATE_KEY",
]
