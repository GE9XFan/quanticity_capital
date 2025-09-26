# Datastore & Persistence

Supports Postgres schema management and data access. See `docs/specs/trade_store.md`.

## Layout
- `migrations/` – Alembic environment + versioned migrations (baseline revision creates schemas `reference`, `trading`, `analytics`, `audit`).
- `models.py` – SQLAlchemy table metadata mirroring the baseline migration for downstream DAL usage.
- `dal.py` – read/write helpers for trades, analytics snapshots, social posts, watchdog reviews.
- `streams.py` – jobs to archive Redis Streams into Postgres.

## Practices
- Keep migrations idempotent; use `alembic` CLI and bump schema/table documentation when contracts change.
- Wrap database operations in transactions; ensure async session usage aligns with SQLAlchemy best practices.
- Update specs (`docs/specs/trade_store.md`) whenever schemas or indices shift.
