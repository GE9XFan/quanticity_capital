# Dashboard Backend

Covers the FastAPI service described in `docs/specs/dashboard_backend.md`.

## Structure
- `api/` – FastAPI app, routers, dependency wiring.
- `schemas.py` – Pydantic response models shared with frontend.
- `services.py` – Redis/Postgres query helpers for health, analytics, trades, social queue.
- `websocket.py` – publish live updates via multiplexed channels.

## Notes
- Secure endpoints with bearer token from `DASHBOARD_API_TOKEN`.
- Expose metrics for Prometheus-friendly scraping once observability module matures.
- Keep responses lean—frontend handles visualization.
