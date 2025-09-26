# Orchestrator (`main.py`)

## Purpose
The orchestrator is the single entry point that wires configuration, logging, Redis, and module
lifecycles. It ensures every enabled subsystem runs under a shared event loop, publishes
heartbeats, aggregates module status, and coordinates graceful shutdown when signalled or when a
module fails.

## Startup Sequence
1. Load the validated `AppConfig` via `core.settings.get_settings()`.
2. Configure structured logging through `core.logging.setup_logging()` (Structlog + stdlib).
3. Acquire the async Redis client from `core.redis.get_redis()`.
4. Instantiate `Orchestrator(settings, redis, logger)` and register signal handlers for
   `SIGINT`/`SIGTERM`.
5. Call `Orchestrator.run()` which creates an `asyncio.TaskGroup` hosting heartbeats,
   the heartbeat monitor, and any enabled modules (scheduler in Phase 2).

## Module Management
- Runtime toggles live in `config/runtime.yml`. The orchestrator maps them to module names and
  tracks three sets internally:
  - `_managed_modules`: running modules supervised by the orchestrator.
  - `_pending_modules`: modules enabled in config but not yet launched.
  - `_disabled_modules`: modules disabled in config.
- Phase 2 launches the scheduler when `modules.scheduler` is `true`; other modules remain pending
  or disabled but are still surfaced in status reporting.
- Each module registers a stop callback so `request_shutdown()` can await `stop()` implementations.

## Heartbeats & Observability
- Heartbeat TTLs are pulled from `config/observability.yml` (`observability.heartbeats`).
- The orchestrator publishes its heartbeat to `system:heartbeat:orchestrator` and expects each
  managed module to emit `system:heartbeat:<module>`.
- `_heartbeat_monitor_loop` runs every ~2 seconds:
  - Reads current heartbeats for orchestrator + managed modules.
  - Emits derived status (`ok`, `stale`, `missing`, `invalid`, `disabled`, `pending`, `stopped`).
  - Writes the aggregate map to the Redis hash `system:heartbeat:status`.
  - Records recovery/degradation events via the `system:events` stream.
- On shutdown the orchestrator marks itself as `stopped` in the status hash while preserving other
  module statuses.

## Failure Escalation & Event Stream
- `_module_wrapper` wraps every module coroutine. If a module raises, the orchestrator:
  1. Logs the crash with `exc_info=True`.
  2. Records a `module_crashed` entry on the `system:events` stream.
  3. Calls `request_shutdown()` which propagates `stop()` to all modules.
  4. Re-raises the exception so callers (and tests) observe the failure.
- Normal lifecycle transitions also write to `system:events` (`orchestrator_start`,
  `shutdown_requested`, `orchestrator_stop`, heartbeat degraded/recovered, etc.).

## Redis Keys Produced
| Key | Description |
| --- | ----------- |
| `system:heartbeat:orchestrator` | ISO timestamp heartbeat set with TTL from observability config. |
| `system:heartbeat:<module>` | Expected heartbeat key for every managed module. |
| `system:heartbeat:status` | Hash of module → status (`ok`, `stale`, `disabled`, `pending`, etc.). |
| `system:events` | Redis Stream capturing lifecycle events, crashes, and shutdown requests. |

## Scheduler Integration (Phase 2)
- When the scheduler toggle is enabled, the orchestrator instantiates
  `Scheduler(config.schedule, redis, heartbeat_ttl)` and supervises it within the same
  `TaskGroup`.
- The scheduler heartbeat (`system:heartbeat:scheduler`) is automatically incorporated into status
  aggregation. When disabled, the orchestrator records `scheduler → disabled` in the status hash.

## Verification Commands
Run these commands against the configured Redis instance to confirm heartbeats and events are
present:

```bash
redis-cli --scan --pattern 'system:heartbeat:*'
redis-cli ttl system:heartbeat:orchestrator
redis-cli hgetall system:heartbeat:status
redis-cli XREAD COUNT 5 STREAMS system:events 0-0
```

`ttl` should report a positive number (seconds remaining) while the orchestrator is running.
`system:heartbeat:status` will include `disabled` entries for modules that are toggled off in
`config/runtime.yml` and `pending` for modules enabled but not yet launched in this phase.

## Runbook Notes
- Prefer `asyncio.run(main())` via `src/quanticity_capital/main.py` to ensure signal handlers are
  attached.
- Before toggling modules, update `config/runtime.yml` and commit the change alongside spec
  updates.
- Keep the observability TTL map in sync with actual heartbeat cadences so stale detection remains
  accurate.
