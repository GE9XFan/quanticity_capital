# Scheduler Module

Implements the token-bucket driven job scheduler described in `docs/specs/scheduler.md` and `docs/specs/scheduler_state.md`.

## Components
- `jobs.py` – job definitions, cron parsing, rotation queues.
- `rate_limits.py` – token bucket logic with persistence hooks.
- `state.py` – read/write Redis hashes (`state:scheduler:*`) for crash recovery.
- `runner.py` – asyncio task group coordinating dispatch, backpressure, and error handling.
- `cli.py` (or commands module) – surfaced via `quanticity_capital.cli` for inspection.

## Contracts
- Publish job events to `stream:schedule:*` with payloads documented in spec.
- Maintain `system:schedule:last_run:<job>` keys and heartbeat metrics.
- Provide APIs for modules to enqueue on-demand jobs without bypassing rate controls.
