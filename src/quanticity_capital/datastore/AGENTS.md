# Datastore & Persistence

Supports Postgres schema management and data access. See `docs/specs/trade_store.md`.

## Layout
- `migrations/` – Alembic environment + versioned migrations.
- `models.py` – SQLAlchemy table metadata (if using ORM) or typed row structures.
- `dal.py` – read/write helpers for trades, analytics snapshots, social posts, watchdog reviews.
- `streams.py` – jobs to archive Redis Streams into Postgres.

## Practices
- Keep migrations idempotent; use `alembic` CLI.
- Wrap database operations in transactions; ensure async session usage aligns with SQLAlchemy best practices.
- Document schema changes in module AGENTS and specs.
