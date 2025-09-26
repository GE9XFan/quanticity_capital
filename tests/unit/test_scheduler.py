import asyncio
import json
from datetime import datetime

import structlog

from quanticity_capital.config.models import (
    ScheduleBucketConfig,
    ScheduleConfig,
    ScheduleJobConfig,
)
from quanticity_capital.scheduler.rate_limits import TokenBucket
from quanticity_capital.scheduler.runner import Scheduler
from tests.utils.fakes import FakeRedis


def test_token_bucket_refill_and_consume() -> None:
    bucket = TokenBucket("test", ScheduleBucketConfig(capacity=2, refill_per_second=1))
    assert bucket.consume() is True
    assert bucket.consume() is True
    assert bucket.consume() is False
    # simulate two seconds passing
    assert bucket.consume(now=bucket.last_refill + 2) is True
    assert bucket.tokens <= bucket.capacity


def test_scheduler_dispatches_jobs_and_updates_state() -> None:
    async def _run() -> None:
        config = ScheduleConfig(
            buckets={"fast": ScheduleBucketConfig(capacity=10, refill_per_second=10)},
            jobs={"demo.job": ScheduleJobConfig(cadence="*/1 * * * * *", bucket="fast")},
        )
        redis = FakeRedis()
        logger = structlog.get_logger("scheduler-test")
        scheduler = Scheduler(config=config, redis=redis, heartbeat_ttl=3, logger=logger)

        task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(1.5)
        await scheduler.stop()
        await asyncio.wait_for(task, timeout=2)

        entries = redis.stream_entries("stream:schedule:demo.job")
        assert entries, "scheduler should dispatch job entries"
        last_run = await redis.get("system:schedule:last_run:demo.job")
        assert last_run is not None
        stored_state = await redis.get("state:scheduler:jobs")
        assert stored_state is not None
        state_payload = json.loads(stored_state)
        assert "demo.job" in state_payload

    asyncio.run(_run())


def test_scheduler_snapshot() -> None:
    async def _run() -> None:
        config = ScheduleConfig(
            buckets={},
            jobs={"heartbeat.job": ScheduleJobConfig(cadence="*/2 * * * * *", bucket=None)},
        )
        redis = FakeRedis()
        scheduler = Scheduler(
            config=config, redis=redis, heartbeat_ttl=2, logger=structlog.get_logger("snap")
        )

        run_task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.5)
        snapshot = scheduler.snapshot()
        assert "heartbeat.job" in snapshot.jobs
        assert isinstance(snapshot.jobs["heartbeat.job"], datetime)
        await scheduler.stop()
        await asyncio.wait_for(run_task, timeout=2)

    asyncio.run(_run())
