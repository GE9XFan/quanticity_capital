# quaticity_capital Package Guide

This package implements the orchestrated trading stack described in `docs/master_plan.md`.

## Structure
- `main.py` – async entrypoint that wires configuration, clients, scheduler, and module tasks.
- `core/` – dependency setup (Redis, Postgres, logging, utility helpers).
- `config/` – Pydantic models + loaders for files in `config/`.
- `scheduler/` – task registry, token buckets, Redis-backed state persistence.
- `ingestion/` – data acquisition workers (Alpha Vantage, IBKR) pushing `raw:*` payloads to Redis.
- `analytics/` – metric computation engine writing `derived:*` keys and analytics streams.
- `signals/` – strategy evaluators producing `signal:*` records.
- `execution/` – order routing to IBKR with risk controls and Postgres persistence.
- `watchdog/` – OpenAI oversight, approval workflows, social commentary.
- `social/` – templating + connectors for outbound channels.
- `dashboard/` – FastAPI backend for monitoring endpoints.
- `observability/` – heartbeat scanner, log management, alert dispatcher.
- `datastore/` – Alembic integration, DAL, archival jobs.
- `cli/` – developer tooling accessible via `uv run python -m quanticity_capital.cli`.

Follow the specs under `docs/specs/` for data contracts, Redis keys, TTLs, and Postgres schemas before implementing modules.
