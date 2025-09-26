# Observability Module

Implements monitors and alerting defined in `docs/specs/observability.md`.

## Components
- `heartbeats.py` – scans `system:heartbeat:*`, triggers alerts when stale.
- `freshness.py` – validates ingestion metadata (`state:ingestion:*`).
- `metrics.py` – aggregates counters and writes to `metrics:*` hashes.
- `alerts.py` – sends Telegram/email notifications per config.
- `logging_config.py` – centralized dictConfig builder for structured logs.

## Expectations
- Run heartbeat/data freshness loops every 15–30 seconds via scheduler jobs.
- Publish health summaries to `state:health:*` keys for dashboard consumption.
- Avoid heavy dependencies; keep loops lightweight to reduce load on orchestrator.
