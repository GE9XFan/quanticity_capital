# Scheduler & Rate Controller

## Purpose
Coordinate timed jobs (ingestion, analytics, housekeeping) with rate-limit enforcement and symbol
rotation. Persist sufficient state in Redis to resume cleanly after restarts and expose inspection
hooks for CLI tooling.

## Components
- `scheduler.rate_limits.TokenBucket` — fractional refill token bucket keyed by `config.schedule`
  buckets.
- `scheduler.jobs.ScheduledJob` — cron-backed job definition with optional rotation queue and
  jitter.
- `scheduler.state` — load/persist helpers for Redis keys:
  - `state:scheduler:jobs`
  - `state:scheduler:buckets`
  - `state:scheduler:rotations`
- `scheduler.runner.Scheduler` — orchestrates heartbeats, dispatch, rotation, and state flushing via
  an `asyncio.TaskGroup` (started/stopped by the orchestrator).

## Runtime Behaviour
- Cron parsing uses `croniter` and supports second-level granularity. Optional jitter randomises
  `next_run` ± `jitter_seconds`.
- Jobs can be attached to rotation queues (`RotationQueue`) which cycle through configured symbol
  lists. The active rotation value is included in the dispatch payload.
- Each job optionally references a token bucket; dispatch proceeds only if `TokenBucket.consume()`
  succeeds. Consumption time is derived from the event loop clock ensuring deterministic refill.
- Dispatch payloads are written to `stream:schedule:<job_id>` via Redis `XADD` and include
  `job`, `scheduled_for`, `dispatched_at`, and optional `rotation` fields.
- Per-job last run timestamps are stored at `system:schedule:last_run:<job_id>` with a TTL matching
  the scheduler heartbeat.
- The scheduler heartbeat key `system:heartbeat:scheduler` is refreshed every few seconds using the
  TTL defined in `observability.heartbeats.scheduler`.
- Internal loops (`_heartbeat_loop`, `_dispatch_loop`, `_state_loop`) respect `Scheduler.stop()` by
  awaiting an `asyncio.Event` so orchestrator-driven shutdown is graceful.

## Persistence & Recovery
- `load_scheduler_state()` pulls JSON blobs from Redis and reconstructs job/bucket state. Missing
  keys fall back to defaults.
- On every flush (default 5s and on shutdown) `persist_scheduler_state()` writes the latest job
  snapshots, bucket levels, and rotation queues.
- `Scheduler.snapshot()` returns an in-memory snapshot (`SchedulerSnapshot`) for CLI inspection
  (jobs → next run `datetime`, buckets → remaining tokens, rotations → symbol order).

## Redis Keys Produced
| Key | Description |
| --- | ----------- |
| `system:heartbeat:scheduler` | Scheduler heartbeat timestamp with TTL. |
| `stream:schedule:<job>` | Redis Stream entries consumed by workers. |
| `system:schedule:last_run:<job>` | ISO timestamp of last dispatch for each job. |
| `state:scheduler:jobs` | JSON map of job → `next_run`. |
| `state:scheduler:buckets` | JSON map of bucket → token count + `last_refill`. |
| `state:scheduler:rotations` | JSON map of job → rotation queue order. |

## Verification Commands
Run these commands while the orchestrator + scheduler are active:

```bash
redis-cli ttl system:heartbeat:scheduler
redis-cli XREAD COUNT 5 STREAMS stream:schedule:<job_id> 0-0
redis-cli GET state:scheduler:jobs | jq
redis-cli GET state:scheduler:buckets | jq
```

Replace `<job_id>` with a configured job (e.g. `demo.job` in tests). `ttl` should show a positive
value indicating an active heartbeat. The JSON blobs will mirror `Scheduler.snapshot()` output and
provide the same data for CLI inspection.

## CLI / Inspection Hooks
- `Scheduler.snapshot()` is the primary in-memory view for CLI commands.
- Future CLI modules should reuse `load_scheduler_state()` to present persisted state even when the
  scheduler is offline.

## Error Handling
- Missing buckets are logged and skip dispatch to avoid unexpected rate-limit violations.
- Redis operations (`XADD`, JSON writes) execute through `core.redis.redis_retry` for transient
  failure resilience.
- On orchestrator shutdown the scheduler flushes state before exiting to prevent job drift.
