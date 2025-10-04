# Project Scope – Phase 0 (REST Capture Only)

The project has been reset to the first milestone: prove that we can call the live Unusual Whales REST API, capture every relevant endpoint for our trading universe (SPY/QQQ/IWM), and store the raw JSON responses. No other modules are in scope until this phase is complete.

## Objectives

1. **Ingest** – Call every REST endpoint listed in `docs/api_queries.md` using real credentials and capture the exact API responses.
2. **Persist** – Save each payload to disk (JSON files under `data/unusual_whales/raw/`) along with metadata so we can replay or audit requests later.
3. **Snapshot** – Maintain the latest payload per endpoint in Redis, following the scheme defined in `docs/storage_plan.md`.
4. **Observe** – Emit structured logs and summary statistics for each run; highlight any failures (rate limits, network errors, unexpected payloads).

## Out of Scope (for now)

- Postgres or long-term Redis history beyond the single snapshot hashes
- WebSocket ingestion
- Analytics, signals, risk, execution, distribution, reporting
- FastAPI services, dashboards, or schedulers
- Docker orchestration beyond what is needed to run the REST fetcher manually

## Current Implementation

- CLI command `make uw-rest-fetch` (or `python -m src.cli.uw_rest_fetch`) that runs through the full endpoint catalogue.
- Endpoint definitions are data-driven (`src/ingestion/uw_endpoints.py`) so additions/removals happen in one place.
- `httpx` client with rate limiting (configurable, defaults to 100 req/min), retry/backoff for 429/5xx, and JSON normalisation.
- Raw output directory structure with per-endpoint indexes to track fetch history.
- Redis snapshot plan defined in `docs/storage_plan.md` (includes which feeds may need history later).
- WebSocket roadmap captured in `docs/websocket_scope.md` so the next phase is already spelled out.
- Documentation in `docs/rest_ingestion.md` describing usage, configuration, monitoring, and output format.

## Configuration

See `src/config/settings.py` for the authoritative list. Key fields:

| Variable | Default | Notes |
|----------|---------|-------|
| `UNUSUAL_WHALES_API_TOKEN` | – | **Required** – retrieved from `.env` | 
| `TARGET_SYMBOLS` | `SPY,QQQ,IWM` | Comma-separated tickers |
| `REQUEST_TIMEOUT_SECONDS` | `30.0` | Per-request timeout |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `100` | Must stay ≤120 |
| `RATE_LIMIT_LEEWAY_SECONDS` | `0.5` | Extra wait inserted between requests |

## Success Criteria

- All endpoints return at least one successful response for each target symbol (where applicable) without hitting hard rate limits.
- Saved JSON files are timestamped, contain the raw body, and include metadata (HTTP status, request timestamp).
- Logs clearly indicate any failures to revisit after the run.

Once these criteria are met consistently, we will scope Phase 1: decide how (and where) to maintain the latest state (Redis, Postgres, etc.), and only then expand into WebSockets and downstream modules.
