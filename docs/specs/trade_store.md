# Trade Persistence & Data Store

## Purpose
Persist trading activity, analytics history, and social outputs into Postgres for long-term storage, reporting, and compliance-lite auditing while keeping Redis lean.

## Responsibilities
- Manage database schema via Alembic migrations.
- Provide data access layer (DAL) for modules to read/write without duplicating SQL logic.
- Archive Redis Streams (analytics, executions, social) into Postgres on configurable intervals.
- Expose query helpers for dashboard/reporting (e.g., latest trades, historical analytics).

## Schema Overview
- `reference.symbols` – symbol metadata, strategy tags, cadence overrides.
- `reference.strategy_config` – thresholds, risk model toggles, parameter JSON.
- `trading.trades` – high-level trade records (signal -> execution -> close).
- `trading.fills` – per fill entries with execution timestamps, price, size.
- `trading.stop_adjustments` – trailing stop modifications.
- `analytics.metric_snapshots` – JSONB column storing metric bundle per symbol/time.
- `analytics.correlation_matrices` – correlation data keyed by group/time.
- `analytics.macro_series` – macro data history.
- `audit.social_posts` – outbound messages, channel, tier, approval metadata.
- `audit.watchdog_reviews` – OpenAI outputs, approval decisions, overrides.
- `audit.integration_runs` – records of integration test executions (start/end, results).

## Data Flow
- Execution engine writes trades/fills as events occur (within transaction to ensure consistency).
- Analytics engine batch inserts metric snapshots every run.
- Social hub logs posts after send/approval.
- Nightly cron (scheduler job) compresses older data partitions as needed.

## Tooling
- Provide CLI migrations: `poetry run alembic upgrade head`.
- Seed scripts to populate symbol universe and default configs.
- `tools/db_check.py` to validate connection, run simple queries.

## Backup & Retention
- Local MacBook: daily `pg_dump` to `backups/` directory (configurable retention 14 days).
- Flag for future Google Cloud: integrate Cloud SQL or managed Postgres with automated backups.

## Integration Testing
- Run migration suite on fresh database.
- Execute sample trade flow to ensure inserts succeed and queries return expected results.
- Validate JSONB column indexes support analytics queries (e.g., by risk score).
