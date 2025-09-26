# Analytics Engine

Align implementation with `docs/specs/analytics_engine.md`.

## Responsibilities
- Consume `raw:*` datasets, validate freshness vs. TTL, compute metrics, and emit `derived:*` outputs + `stream:analytics` events.
- Plugin architecture: register metric components under `metrics/` with clear input/output contracts.
- Persist aggregates to Postgres via `datastore` helpers.

## Planned Modules
- `engine.py` – orchestrates metric execution per scheduler trigger.
- `context.py` – caches shared data (vol surfaces, symbol metadata) within run cycle.
- `metrics/` – individual metric implementations (dealer exposure, VPIN, volatility regime, etc.).
- `publisher.py` – writes to Redis, handles quality flags.

## Testing
- Unit test metric math under `tests/unit/analytics`.
- Integration tests should hydrate sample data into Redis and assert outputs + TTL.
