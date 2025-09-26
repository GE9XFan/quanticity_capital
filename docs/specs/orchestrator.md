# Orchestrator (`main.py`)

## Purpose
Provide a single entry point that initializes configuration, dependencies, and module task loops, ensuring every subsystem runs under a unified event loop with graceful shutdown and observability.

## Responsibilities
- Bootstrap configuration, logging, and dependency clients (Redis, Postgres, HTTP, IBKR gateway, OpenAI, social APIs).
- Spawn and supervise module tasks (scheduler, ingestion workers, analytics engine, signal engine, execution manager, watchdog, social dispatcher, dashboard API).
- Maintain lifecycle hooks: startup sequencing, health checks, graceful teardown on signals/uncaught errors.
- Publish orchestrator heartbeat (`system:heartbeat:orchestrator`) and aggregate module health for dashboard/API consumption.

## Inputs & Dependencies
- `.env` / YAML config files for credentials, symbol sets, cadences.
- Redis connection (async) and Postgres connection pool.
- Scheduler task definitions from `config/schedule.yml`.
- Module factories providing async task coroutines.

## Outputs
- log entries (structured JSON) describing startup, task transitions, failures.
- `system:heartbeat:*` keys for orchestrator and child modules.
- `system:events` Redis Stream for major lifecycle events (start/stop/error).

## Key Behaviors
- **Startup Order:** configuration → logging → Redis → Postgres → scheduler → ingestion modules → analytics → signals → execution → watchdog → social → dashboard.
- **Task Supervision:** use `asyncio.TaskGroup` (Python 3.11) for structured concurrency; restart policies configurable per module.
- **Graceful Shutdown:** handles `SIGINT`/`SIGTERM`, notifies modules, flushes pending social posts, closes network connections, and deregisters IBKR subscriptions.
- **Failure Handling:** on unrecoverable module failure, emit alert event and decide to restart task or exit entire orchestrator depending on severity.

## Configuration
- `config/runtime.yml`: toggles for modules (enable/disable), concurrency levels, restart policies.
- `config/symbols.yml`: shared symbol universe, TTL overrides.
- `config/credentials.example`: env var mapping for secrets.

## Observability
- Emits heartbeat every 10s.
- Aggregates module heartbeats and exposes via dashboard API endpoint `/health`.
- Logs module start/stop durations and failure stack traces.

## Integration Testing
- Launch orchestrator in paper-trading mode with Alpha Vantage live keys; verify health endpoints and heartbeat keys.
- Confirm orchestrator recovers from forced module failure (simulate exception) and logs restart.
