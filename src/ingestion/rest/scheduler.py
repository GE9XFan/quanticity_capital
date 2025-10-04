"""Asynchronous scheduler for Unusual Whales REST ingestion."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Iterable

from .client import RestClient
from .jobs import RestJobDefinition, RestRequestSpec, build_job_catalog
from ..config import IngestionSettings
from ..persistence.postgres import PostgresRepository
from ..rate_limit import TokenBucket

LOGGER = logging.getLogger(__name__)


class RestScheduler:
    """Periodically execute REST jobs respecting rate limits."""

    def __init__(
        self,
        settings: IngestionSettings,
        client: RestClient,
        repository: PostgresRepository,
        limiter: TokenBucket,
    ) -> None:
        self._settings = settings
        self._client = client
        self._repository = repository
        self._limiter = limiter
        self._jobs: list[RestJobDefinition] = build_job_catalog(settings)
        self._last_run: dict[str, float] = {job.name: 0.0 for job in self._jobs}
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the scheduler loop."""

        await self._client.start()
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run())

    async def stop(self) -> None:
        """Stop the scheduler."""

        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._client.close()

    async def _run(self) -> None:
        poll_interval = self._settings.rest_job_poll_interval
        try:
            while not self._stop_event.is_set():
                now = time.monotonic()
                for job in self._jobs:
                    if self._should_run(job, now):
                        await self._execute_job(job)
                        self._last_run[job.name] = now
                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:  # pragma: no cover - cancellation path
            LOGGER.info("REST scheduler cancelled")
            raise

    def _should_run(self, job: RestJobDefinition, now: float) -> bool:
        last = self._last_run.get(job.name, 0.0)
        return (now - last) >= job.cadence_seconds

    async def _execute_job(self, job: RestJobDefinition) -> None:
        try:
            requests = list(job.request_builder(self._settings))
        except Exception as exc:  # pragma: no cover - defensive guard
            LOGGER.exception("Failed to build requests for job %s: %s", job.name, exc)
            return

        for request in requests:
            try:
                await self._run_request(job, request)
            except Exception as exc:  # pragma: no cover - ingestion resilience
                LOGGER.exception("Job %s request %s failed: %s", job.name, request.name, exc)

    async def _run_request(self, job: RestJobDefinition, request: RestRequestSpec) -> None:
        attempt = 0
        backoff = 10
        while True:
            attempt += 1
            await self._limiter.acquire(request.tokens)
            response = await self._client.get(request.path, params=request.params)
            if response.status_code == 429:
                LOGGER.warning("Rate limited on %s (attempt %d)", request.name, attempt)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 120)
                if attempt >= 3:
                    return
                continue
            try:
                response.raise_for_status()
            except Exception:
                LOGGER.error("HTTP error on %s: %s", request.name, response.text[:200])
                raise
            payload = response.json()
            await job.processor(payload, request, self._repository)
            return

    @property
    def jobs(self) -> Iterable[RestJobDefinition]:
        return tuple(self._jobs)
