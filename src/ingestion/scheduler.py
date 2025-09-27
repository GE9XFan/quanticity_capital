"""Ingestion scheduler wiring."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from queue import Queue

from redis import Redis
from structlog.stdlib import BoundLogger

from src.analytics.config import AnalyticsJobConfig, load_analytics_config
from src.core.config import AnalyticsConfig


class IngestionScheduler:
    """Coordinator that feeds analytics jobs into background workers."""

    def __init__(
        self,
        *,
        redis_client: Redis,
        logger: BoundLogger,
        analytics: AnalyticsConfig,
        queue_key: str | None = None,
    ) -> None:
        self._redis = redis_client
        self._logger = logger.bind(component="ingestion_scheduler")
        self._analytics = analytics
        self._queue_key = queue_key or "queue:analytics"
        self._task_queue: Queue[AnalyticsJobConfig | None] | None = None
        self._workers: list[threading.Thread] = []

    def bootstrap(self) -> None:
        """Prepare scheduler resources and emit initial status."""

        self._logger.info(
            "scheduler_bootstrap",
            analytics_enabled=self._analytics.enabled,
            max_workers=self._analytics.max_workers,
            task_queue_size=self._analytics.task_queue_size,
        )

    def start(self) -> None:
        """Load analytics jobs and dispatch them through worker threads."""

        if not self._analytics.enabled:
            self._logger.info("scheduler_skipped", reason="analytics_disabled")
            return

        jobs_bundle = load_analytics_config(self._analytics.config_path)
        jobs = tuple(job for job in jobs_bundle.enabled())
        if not jobs:
            self._logger.info("scheduler_no_jobs", config_path=self._analytics.config_path)
            return

        worker_count = min(self._analytics.max_workers, len(jobs))
        task_queue: Queue[AnalyticsJobConfig | None] = Queue(
            maxsize=self._analytics.task_queue_size
        )

        def worker() -> None:
            while True:
                job = task_queue.get()
                if job is None:
                    task_queue.task_done()
                    break
                try:
                    self._process_job(job)
                except Exception as exc:  # pragma: no cover - defensive logging
                    self._logger.error(
                        "scheduler_job_failed",
                        job=job.as_dict(),
                        error=str(exc),
                    )
                finally:
                    task_queue.task_done()

        self._logger.info(
            "scheduler_started",
            config_path=self._analytics.config_path,
            worker_count=worker_count,
            job_count=len(jobs),
        )

        workers: list[threading.Thread] = []
        for index in range(worker_count):
            thread = threading.Thread(
                target=worker,
                name=f"ingestion-worker-{index}",
                daemon=True,
            )
            thread.start()
            workers.append(thread)

        for job in jobs:
            task_queue.put(job)

        task_queue.join()

        for _ in workers:
            task_queue.put(None)
        for thread in workers:
            thread.join(timeout=1)

        self._logger.info("scheduler_completed", jobs_processed=len(jobs))

        self._task_queue = task_queue
        self._workers = workers

    def _process_job(self, job: AnalyticsJobConfig) -> None:
        """Placeholder job processor for analytics refresh."""

        message = {
            "job": job.as_dict(),
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": 0,
        }
        payload = json.dumps(message)
        self._redis.rpush(self._queue_key, payload)
        self._logger.info(
            "scheduler_enqueued_job",
            queue_key=self._queue_key,
            job=job.as_dict(),
        )


__all__ = ["IngestionScheduler"]
