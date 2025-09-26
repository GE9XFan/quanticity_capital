# Scheduler & Rate Controller

## Purpose
Coordinate timed tasks for all external data sources and internal analytics, ensuring compliance with rate limits, symbol rotation requirements, and Redis TTL guarantees.

## Responsibilities
- Manage job queues for Alpha Vantage endpoints, IBKR subscriptions, analytics refreshes, social cadences, and housekeeping tasks.
- Enforce per-endpoint rate limits using token buckets with configurable refill rates.
- Persist scheduler state for crash recovery (next run time, queued jobs, token levels) in Redis.
- Provide introspection APIs/CLI commands to inspect schedules and adjust cadences at runtime.

## Inputs
- Scheduler configuration (`config/schedule.yml`) defining jobs, cadences, jitter, priority, and rate buckets.
- Symbol metadata (`config/symbols.yml`) including groupings (Techascope, ETFs, futures) and overrides.
- Redis for state persistence and inter-module signaling.

## Outputs
- Job dispatch events posted to Redis Streams (`stream:schedule:*`) consumed by ingestion and analytics workers.
- `system:schedule:last_run:<job>` keys storing timestamps of last execution.
- Rate-limit statistics logged periodically.

## Core Concepts

- Cron expressions rely on the `croniter` package; install `croniter>=3.0.3` to enable schedule parsing.
- **Token Buckets:** settings for Alpha Vantage global (600 cpm), per-endpoint caps, and IBKR request pacing. Stored under `system:ratelimit:<bucket>`.
- **Rotation Queues:** maintain arrays of symbols (e.g., level-2 groups). After dispatch, symbol moved to end of queue.
- **Backpressure:** if consumer reports failure, scheduler delays next run and increments failure metrics.
- **On-Demand Jobs:** modules can enqueue ad-hoc fetches (e.g., new trade symbol) via `scheduler.enqueue(job_id, params)`.
- **State Persistence:** bucket and job metadata replicated to Redis hashes (`state:scheduler:*`) for crash recovery and inspection.

## Job Families & Defaults
- `av.realtime_options`: 12s cadence, jitter ±2s, bucket `av_high_freq`.
- `av.tech_indicators`: 60s cadence, bucket `av_medium_freq`.
- `av.analytics_window`: 5m cadence, bucket `av_bulk`.
- `av.news`: 10m cadence.
- `av.macro`: 6h cadence (per metric).
- `ibkr.l2_rotation`: 5s cadence per trio.
- `ibkr.account_snapshot`: 15s cadence.
- `analytics.refresh`: 10s cadence for primary metrics, others 60s+.
- `signals.evaluate`: 10s cadence per strategy.
- `watchdog.review`: triggered by signals, plus periodic 1m review for outstanding items.
- `social.dispatch`: 30s poll for queue + scheduled blasts at configured times.

## Error Handling
- Track consecutive failures per job; after threshold, escalate to orchestrator for manual intervention.
- Auto-throttle on HTTP 429/IBKR pacing violations by reducing token refill temporarily.

## Integration Testing
- Simulate scheduler run with live Alpha Vantage keys; log actual fetch timestamps vs. configured cadence.
- Force rate-limit exceed scenario to verify backoff logic (mock by lowering bucket limit temporarily).
- Validate state recovery: stop orchestrator mid-run, restart, confirm scheduler resumes without losing timing.
