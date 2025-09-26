# Core Utilities

Provide shared infrastructure primitives so feature modules stay thin.

## Components
- `settings.py` – wraps `config.loader.load_settings` and exposes `get_settings()` with cache-aware reloads.
- `redis.py` – async Redis client factory with retry/backoff, JSON helpers, TTL utilities, and index maintenance helpers used by ingestion/scheduler modules.
- `postgres.py` – SQLAlchemy async engine + sessionmaker factory with context-managed session scopes for DAL consumers.
- `models.py` – shared Pydantic domain objects (options chains, analytics bundles, signals, orders, social posts).
- `logging.py` – structured logging bootstrap consistent with `config/observability.yml` (pending implementation).

## Guidelines
- No module-specific logic here—only reusable clients/utilities.
- Retry/backoff utilities and TTL/index helpers should remain side-effect free and reusable across modules.
- Keep functions async-aware; avoid blocking Redis or database calls.
- Factories should accept optional `AppConfig` arguments so integration tests can inject temporary settings bundles.
- Update domain models alongside specs when contracts change; downstream modules rely on these schemas.
