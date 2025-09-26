# Core Utilities

Provide shared infrastructure primitives so feature modules stay thin.

## Components
- `settings.py` – wraps `config.loader.load_settings` and exposes `get_settings()` with cache-aware reloads.
- `redis.py` – async Redis client factory with cached connection + teardown helper (TTL helpers TBD).
- `postgres.py` – SQLAlchemy async engine factory/teardown; session helpers to follow once ORM wiring begins.
- `logging.py` – structured logging bootstrap consistent with `config/observability.yml` (pending implementation).

## Guidelines
- No module-specific logic here—only reusable clients/utilities.
- Include lightweight retry/backoff helpers used across ingestion/analytics.
- Keep functions async-aware; avoid blocking Redis or database calls.
- Factories should accept optional `AppConfig` arguments so integration tests can inject temporary settings bundles.
