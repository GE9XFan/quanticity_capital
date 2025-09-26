"""Orchestrator entrypoint.

Loads configuration, initializes shared clients, and spins up module task groups.
See docs/specs/orchestrator.md for the runtime contract.
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, Optional

import structlog

from .config.models import AppConfig
from .core.logging import setup_logging
from .core.redis import RetryConfig, close_redis, get_redis, redis_retry
from .core.settings import get_settings
from .scheduler import Scheduler

HEARTBEAT_STATUS_KEY = "system:heartbeat:status"
EVENT_STREAM_KEY = "system:events"


class Orchestrator:
    """Coordinates module lifecycles and observability."""

    def __init__(
        self,
        *,
        settings: AppConfig,
        redis,
        logger: structlog.stdlib.BoundLogger,
    ) -> None:
        self.settings = settings
        self.redis = redis
        self.logger = logger
        self._shutdown_event = asyncio.Event()
        self._task_group: Optional[asyncio.TaskGroup] = None
        self._module_stop_callbacks: Dict[str, Callable[[], Awaitable[None]]] = {}
        self._managed_modules: set[str] = set()
        self._pending_modules = self._initial_pending_modules()
        self._disabled_modules = self._initial_disabled_modules()
        self._status_cache: Dict[str, str] = {}
        self._retry_config = RetryConfig()
        self._heartbeat_ttl = {
            name: int(ttl) for name, ttl in settings.observability.heartbeats.items()
        }

    async def run(self) -> None:
        self.logger.info("orchestrator starting")
        await self._record_event("orchestrator_start")
        try:
            async with asyncio.TaskGroup() as tg:
                self._task_group = tg
                self._managed_modules.add("orchestrator")
                tg.create_task(self._heartbeat_loop(), name="heartbeat")
                tg.create_task(self._heartbeat_monitor_loop(), name="heartbeat-monitor")
                self._launch_modules(tg)
        finally:
            self._task_group = None
            await self._record_event("orchestrator_stop")
            self.logger.info("orchestrator stopped")

    async def request_shutdown(self, reason: str | None = None) -> None:
        if self._shutdown_event.is_set():
            return
        self._shutdown_event.set()
        self.logger.info("shutdown requested", reason=reason)
        await self._record_event("shutdown_requested", detail=reason)
        for name, stop_cb in list(self._module_stop_callbacks.items()):
            try:
                await stop_cb()
            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.warning("module stop failed", module=name, error=str(exc))

    def _initial_pending_modules(self) -> set[str]:
        pending = {name for name, enabled in self._module_enabled_map().items() if enabled}
        pending.discard("orchestrator")
        return pending

    def _initial_disabled_modules(self) -> set[str]:
        return {name for name, enabled in self._module_enabled_map().items() if not enabled}

    def _module_enabled_map(self) -> Dict[str, bool]:
        modules = self.settings.runtime.modules
        return {
            "orchestrator": True,
            "scheduler": modules.scheduler,
            "ingestion_alpha_vantage": modules.ingestion.alpha_vantage,
            "ingestion_ibkr": modules.ingestion.ibkr,
            "analytics": modules.analytics,
            "signal_engine": modules.signals,
            "execution": modules.execution,
            "watchdog": modules.watchdog,
            "social_hub": modules.social,
            "dashboard_api": modules.dashboard_api,
        }

    def _launch_modules(self, task_group: asyncio.TaskGroup) -> None:
        modules = self.settings.runtime.modules
        if modules.scheduler:
            scheduler_logger = self.logger.bind(module="scheduler")
            scheduler = Scheduler(
                config=self.settings.schedule,
                redis=self.redis,
                heartbeat_ttl=self._heartbeat_ttl.get("scheduler", 5),
                logger=scheduler_logger,
            )
            self._managed_modules.add("scheduler")
            self._pending_modules.discard("scheduler")
            self._module_stop_callbacks["scheduler"] = scheduler.stop
            task_group.create_task(
                self._module_wrapper("scheduler", scheduler.start()), name="scheduler"
            )
        else:
            self._disabled_modules.add("scheduler")
            self.logger.info("scheduler disabled by configuration")

    async def _module_wrapper(self, name: str, coro) -> None:
        try:
            await coro
        except asyncio.CancelledError:  # pragma: no cover - structured concurrency cancellation
            raise
        except Exception as exc:
            self.logger.error("module crashed", module=name, error=str(exc), exc_info=True)
            await self._record_event("module_crashed", module=name, detail=str(exc))
            await self.request_shutdown(reason=f"module {name} crashed")
            raise
        finally:
            self.logger.info("module exited", module=name)

    async def _heartbeat_loop(self) -> None:
        ttl = self._heartbeat_ttl.get("orchestrator", 10)
        key = "system:heartbeat:orchestrator"
        while not self._shutdown_event.is_set():
            now = datetime.now(tz=timezone.utc).isoformat()
            await self.redis.set(key, now, ex=ttl)
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=max(ttl / 2, 1))
            except asyncio.TimeoutError:
                continue
        await self.redis.set(key, datetime.now(tz=timezone.utc).isoformat(), ex=ttl)

    async def _heartbeat_monitor_loop(self) -> None:
        interval = 2.0
        while not self._shutdown_event.is_set():
            statuses = await self._collect_statuses()
            if statuses:
                await self.redis.hset(HEARTBEAT_STATUS_KEY, mapping=statuses)
                await self._handle_status_transitions(statuses)
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
        await self.redis.hset(HEARTBEAT_STATUS_KEY, mapping={"orchestrator": "stopped"})

    async def _collect_statuses(self) -> Dict[str, str]:
        results: Dict[str, str] = {}
        monitored = {"orchestrator", *self._managed_modules}
        now = datetime.now(tz=timezone.utc)
        for module in monitored:
            ttl = self._heartbeat_ttl.get(module)
            if ttl is None:
                continue
            key = f"system:heartbeat:{module}"
            value = await self.redis.get(key)
            if value is None:
                results[module] = "missing"
                continue
            try:
                heartbeat_at = datetime.fromisoformat(value)
            except ValueError:
                results[module] = "invalid"
                continue
            age = (now - heartbeat_at).total_seconds()
            results[module] = "ok" if age <= ttl else "stale"
        for module in self._disabled_modules:
            results[module] = "disabled"
        for module in self._pending_modules:
            results[module] = "pending"
        return results

    async def _handle_status_transitions(self, statuses: Dict[str, str]) -> None:
        for module, status in statuses.items():
            previous = self._status_cache.get(module)
            if status == previous:
                continue
            self._status_cache[module] = status
            if status in {"stale", "missing", "invalid"}:
                self.logger.warning("heartbeat degraded", module=module, status=status)
                await self._record_event("heartbeat_degraded", module=module, detail=status)
            elif status == "ok" and previous in {"stale", "missing", "invalid"}:
                self.logger.info("heartbeat recovered", module=module)
                await self._record_event("heartbeat_recovered", module=module)

    async def _record_event(
        self,
        event_type: str,
        *,
        module: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        payload = {
            "event": event_type,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        if module is not None:
            payload["module"] = module
        if detail is not None:
            payload["detail"] = detail

        async def _xadd():
            return await self.redis.xadd(EVENT_STREAM_KEY, payload)  # type: ignore[arg-type]

        with suppress(Exception):
            await redis_retry(_xadd, retry_config=self._retry_config, logger=self.logger)


async def _async_main() -> None:
    settings = get_settings()
    logger = setup_logging(settings)
    redis = await get_redis(settings)
    orchestrator = Orchestrator(settings=settings, redis=redis, logger=logger)

    loop = asyncio.get_running_loop()
    shutdown_signals = (signal.SIGINT, signal.SIGTERM)

    def _signal_handler(sig: signal.Signals) -> None:
        loop.create_task(orchestrator.request_shutdown(reason=f"signal:{sig.name}"))

    for sig in shutdown_signals:
        with suppress(NotImplementedError):  # pragma: no cover - Windows fallback
            loop.add_signal_handler(sig, _signal_handler, sig)

    try:
        await orchestrator.run()
    finally:
        for sig in shutdown_signals:
            with suppress(NotImplementedError):
                loop.remove_signal_handler(sig)
        await orchestrator.request_shutdown("process exiting")
        await close_redis()


def main() -> None:
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:  # pragma: no cover - handled via signal handler
        pass


if __name__ == "__main__":
    main()
