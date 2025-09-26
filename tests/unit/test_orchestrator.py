import asyncio

import pytest
import structlog

from quanticity_capital.main import Orchestrator
from tests.utils.fakes import FakeRedis


class DummyModules:
    def __init__(self) -> None:
        self.scheduler = True
        self.ingestion = type("Ingestion", (), {"alpha_vantage": True, "ibkr": False})()
        self.analytics = False
        self.signals = False
        self.execution = False
        self.watchdog = False
        self.social = False
        self.dashboard_api = False


class DummyRuntime:
    def __init__(self) -> None:
        self.modules = DummyModules()


class DummyObservability:
    def __init__(self) -> None:
        self.heartbeats = {"orchestrator": 2, "scheduler": 2}


class DummySchedule:
    def __init__(self) -> None:
        self.buckets = {}
        self.jobs = {}


class StubConfig:
    def __init__(self) -> None:
        self.runtime = DummyRuntime()
        self.observability = DummyObservability()
        self.schedule = DummySchedule()


async def _run_orchestrator(orchestrator: Orchestrator, duration: float = 1.0) -> None:
    run_task = asyncio.create_task(orchestrator.run())
    await asyncio.sleep(duration)
    await orchestrator.request_shutdown("test complete")
    await asyncio.wait_for(run_task, timeout=5)


def _build_config() -> StubConfig:
    return StubConfig()


def test_orchestrator_heartbeat_and_status_reporting() -> None:
    async def _run() -> None:
        redis = FakeRedis()
        config = _build_config()
        logger = structlog.get_logger("test-orchestrator")
        orchestrator = Orchestrator(settings=config, redis=redis, logger=logger)

        await _run_orchestrator(orchestrator, duration=1.5)

        status = await redis.hgetall("system:heartbeat:status")
        assert status.get("orchestrator") in {"ok", "stopped"}
        assert status.get("scheduler") in {"ok", "pending", "disabled", "missing"}

    asyncio.run(_run())


def test_orchestrator_escalates_module_crash() -> None:
    async def _run() -> None:
        redis = FakeRedis()
        config = _build_config()
        logger = structlog.get_logger("test-orchestrator-crash")
        orchestrator = Orchestrator(settings=config, redis=redis, logger=logger)

        async def failing_module() -> None:
            raise RuntimeError("boom")

        orchestrator._managed_modules.add("failing")
        orchestrator._heartbeat_ttl["failing"] = 1
        orchestrator._module_stop_callbacks["failing"] = lambda: asyncio.sleep(0)

        async def wrapper() -> None:
            await orchestrator._module_wrapper("failing", failing_module())

        with pytest.raises(RuntimeError):
            await wrapper()
        assert orchestrator._shutdown_event.is_set()

    asyncio.run(_run())
