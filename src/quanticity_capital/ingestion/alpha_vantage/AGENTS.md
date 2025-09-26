# Alpha Vantage Ingestion

Reset plan lives in `docs/specs/ingestion_alpha_vantage.md`. Implement scoped endpoints only (realtime options, indicators, news) before expanding.

## Implementation Notes
- Controller listens for scheduler events `av.realtime_options`, `av.tech_indicators`, `av.news`.
- Enforce capability map from `config/symbols.yml`; skip unsupported symbols gracefully.
- Use shared HTTP client with exponential backoff (1s, 3s, 7s) and cooldown on repeated failures.
- Persist payloads to Redis using `raw:options:<symbol>`, `raw:indicator:<symbol>:<indicator>`, and `raw:news:equities` with TTL = 2 × cadence.
- Update `state:ingestion:options:<symbol>` heartbeats for observability monitor.

## Files to Add
- `client.py` – session factory, request helpers, json validation.
- `jobs.py` – individual fetch handlers invoked by scheduler.
- `schemas.py` – Pydantic models for response normalization (optional but encouraged).
