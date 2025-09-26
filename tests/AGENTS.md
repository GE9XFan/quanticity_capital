# Tests Directory Guide

## Layout
- `unit/` – fast tests for pure functions (e.g., metric calculations, sizing math).
- `integration/` – requires Redis/Postgres/third-party APIs. Gate with `pytest -m integration`.
- `e2e/` – orchestrator-level dry runs (paper trading). Run sparingly due to rate limits.

## Practices
- Use pytest markers: `@pytest.mark.integration`, `@pytest.mark.e2e`.
- Avoid mocking live services in integration tests; instead sandbox requests (paper accounts, staging webhooks).
- Record fixtures in `docs/test-records/` when capturing payloads for regression.
- Clean up Redis keys between tests to keep TTL-driven assumptions stable.
