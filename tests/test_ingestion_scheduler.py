from __future__ import annotations

import json

import structlog

from src.core.config import AnalyticsConfig
from src.ingestion.scheduler import IngestionScheduler


class DummyRedis:
    def __init__(self) -> None:
        self.commands: list[tuple[str, str]] = []

    def ping(self) -> None:  # pragma: no cover - not used in tests
        return None

    def rpush(self, key: str, value: str) -> None:
        self.commands.append((key, value))


def test_scheduler_processes_enabled_jobs(tmp_path):
    analytics_config_path = tmp_path / "analytics.yml"
    analytics_config_path.write_text(
        """
        jobs:
          - name: job_one
            type: analytics.test
            symbols: [SPY]
            metrics: [dealer]
          - name: job_two
            type: analytics.test
            enabled: false
            symbols: [QQQ]
            metrics: [dealer]
          - name: job_three
            type: analytics.test
            symbols: [IWM]
            metrics: [dealer]
        """
    )

    analytics_config = AnalyticsConfig(
        enabled=True,
        config_path=str(analytics_config_path),
        max_workers=2,
        task_queue_size=8,
        stale_after_seconds=45,
    )

    logger = structlog.get_logger("test")
    redis_client = DummyRedis()
    scheduler = IngestionScheduler(
        redis_client=redis_client,
        logger=logger,
        analytics=analytics_config,
    )

    scheduler.bootstrap()
    scheduler.start()

    assert len(redis_client.commands) == 2

    queued_names = {
        json.loads(payload)["job"]["name"]
        for _, payload in redis_client.commands
    }
    assert queued_names == {"job_one", "job_three"}


def test_scheduler_skips_when_disabled(tmp_path):
    analytics_config = AnalyticsConfig(
        enabled=False,
        config_path=str(tmp_path / "missing.yml"),
        max_workers=1,
        task_queue_size=4,
        stale_after_seconds=45,
    )

    logger = structlog.get_logger("test")
    scheduler = IngestionScheduler(
        redis_client=DummyRedis(),
        logger=logger,
        analytics=analytics_config,
    )

    scheduler.bootstrap()
    scheduler.start()
