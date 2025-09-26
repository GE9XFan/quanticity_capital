# Dashboard Backend (API Service)

## Purpose
Expose a lightweight HTTP/WebSocket API that aggregates system state from Redis/Postgres for consumption by the React dashboard and external tools.

## Responsibilities
- Serve REST endpoints for health, data freshness, active trades, analytics snapshots, social queue, watchdog reviews, scheduler status.
- Offer WebSocket streams for live updates (ingestion health, trade updates, social approvals).
- Enforce simple authentication (bearer token) configurable in `.env`.
- Provide pagination/filtering for historical queries (trades, analytics history).

## Technology
- FastAPI with uvicorn for async support.
- Redis async client for hot data; SQLAlchemy async session for Postgres reads.
- Pydantic response models for consistent schemas.

## Core Endpoints
- `GET /health`: module heartbeats, scheduler status, Redis/Postgres connectivity.
- `GET /symbols`: list of configured symbols + cadences.
- `GET /analytics/{symbol}`: latest analytics bundle.
- `GET /signals/active`: active/pending signals with metadata.
- `GET /trades/live`: current positions and PnL.
- `GET /trades/history`: paginated historical trades.
- `GET /social/pending`: queued messages awaiting approval.
- `GET /watchdog/reviews`: recent watchdog outputs.
- `GET /scheduler/queues`: snapshot of job queues and token buckets.
- `POST /social/approve`: manual approval (if not using Telegram) – optional.
- WebSocket `/ws/stream`: multiplexed channels (analytics, signals, trades, heartbeats).

## Data Access Patterns
- Use Redis for latest state; fallback to Postgres when data missing or historical range requested.
- Cache heavy queries (e.g., correlation matrix) in Redis with short TTL (30s) to avoid repeated DB hits.

## Observability
- Heartbeat `system:heartbeat:dashboard_api` 15s.
- Logs within `logs/dashboard_api.log` including request timing.
- Metrics: request count, response time, error rate.

## Integration Testing
- Start API locally with running Redis/Postgres; hit endpoints to verify schema.
- Test WebSocket stream for updates triggered by mock events.
- Validate auth by attempting requests with invalid token.
