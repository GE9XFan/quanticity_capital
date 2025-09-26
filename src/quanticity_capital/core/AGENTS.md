# Core Utilities

Provide shared infrastructure primitives so feature modules stay thin.

## Planned Components
- `redis.py` – async client factory, TTL helpers, Redis stream wrappers (see `docs/master_plan.md` TTL table).
- `postgres.py` – SQLAlchemy async engine setup, session management, Alembic integration helpers.
- `logging.py` – structured logging bootstrap consistent with `config/observability.yml`.
- `settings.py` – central object bundling loaded configuration for dependency injection.

## Guidelines
- No module-specific logic here—only reusable clients/utilities.
- Include lightweight retry/backoff helpers used across ingestion/analytics.
- Keep functions async-aware; avoid blocking Redis or database calls.
