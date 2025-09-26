# Implementation Plan (September 2025 Reset)

## Phase 0 – Local Environment (Day 0)
- Install Python 3.11 (homebrew or python.org) and create a dedicated virtual environment with `python3.11 -m venv .venv` at the repo root.
- Activate the venv for every session (`source .venv/bin/activate` on macOS) and upgrade tooling with `python -m pip install --upgrade pip`.
- Create `.env` for secrets and `.env.example` with placeholder values (`ALPHAVANTAGE_API_KEY`, `REDIS_URL`, `IBKR_*`, `LOG_LEVEL`). Document the load order in the README.
- Add a plain `requirements.txt` that starts with the minimal base stack: `httpx`, `redis`, `pydantic`, `python-dotenv`, `structlog`, `pytest`. Append new libraries only when they are introduced in code; regenerate the file manually to keep it readable.
- Record the bootstrap commands in `docs/setup.md` (activate venv, install requirements, run lint/tests) so future tasks never rely on `uv`, `poetry`, or other tooling.

## Phase 1 – Repository Skeleton (Day 0-1)
- Create the top-level layout: `src/`, `src/ingestion/`, `src/core/` (shared utilities), `config/`, `tests/`, `docs/` (already present).
- Add `src/main.py` with a stubbed CLI that wires environment loading (`python-dotenv`) and a Redis connection placeholder.
- Establish `config/runtime.json` (or YAML) with Redis connection defaults and feature toggles; ensure the loader reads `.env` first and falls back to sane defaults.
- Configure basic linters only if needed (e.g., `ruff`) via an optional `pyproject.toml` section—keep tooling minimal to avoid setup friction.
- Document filesystem expectations, naming conventions, and how modules should read configuration so future features slot in consistently.

## Phase 2 – Alpha Vantage Ingestion (Sequential Iterations)
- Adopt a strict one-endpoint-at-a-time workflow. Before any code is written, request from the user:
  - Endpoint name and target symbols/series.
  - Exact query parameters (function, interval, datatype, pagination, etc.).
  - A real JSON sample or cURL response to validate shape.
  - Expected refresh cadence and the TTL that should be applied in Redis.
- Create a tracking table (`docs/alpha_vantage_endpoints.md`) to log progress: requested, parameters received, implemented, validated in Redis.
- For each endpoint iteration:
  1. Capture configuration in `config/alpha_vantage.yml` under a unique key.
  2. Implement a single fetch module in `src/ingestion/alpha_vantage/<endpoint>.py` using `httpx` with retry/backoff helpers from `src/core/http.py`.
  3. Store payloads in Redis using the agreed key pattern (`raw:alpha_vantage:<endpoint>[:<symbol>]`) and TTL confirmed with the user. Persist the raw response plus metadata (`as_of`, `ttl_applied`, `request_params`).
  4. Validate manually: run the module, dump the Redis key, and capture the result in `docs/verification/<endpoint>_<date>.json`.
  5. Only move to the next endpoint after the user signs off on fetch correctness, storage layout, and expiry behaviour.
- Initial endpoint order (adjustable once requirements are confirmed):
  1. `REALTIME_OPTIONS` for ETFs.
  2. `TIME_SERIES_INTRADAY` (base price feed backing indicators).
  3. `TOP_GAINERS_LOSERS`.
  4. `NEWS_SENTIMENT`.

## Phase 3 – Interactive Brokers Connectivity (Post-AV Sign-off)
- Review the latest handshake requirements with the user (preferred API—`ib_insync` vs native). Document connection parameters in `.env` and configuration files before touching code.
- Implement connection management inside `src/ingestion/ibkr/` with session lifecycle, reconnect, and heartbeat logging to Redis (`state:ibkr:*`).
- Expose a manual test script (`python -m src.ingestion.ibkr.cli --account`) that the user can run to verify credentials and basic data persistence before automation begins.
- Mirror the AV workflow: one data stream at a time (account summary → positions → top-of-book → level 2), each validated with captured Redis snapshots prior to expanding scope.

## Phase 4 – Analytics Foundations (After AV + IBKR Data Stable)
- Stand up analytics only once both ingestion pipelines are populating Redis reliably.
- Define analytics inputs in a configuration file (`config/analytics.yml`) that references the Redis keys created during AV/IBKR phases.
- Implement analytics modules incrementally, starting with the minimum viable calculations needed for downstream signals. Each module writes to `derived:*` keys with TTLs confirmed alongside the user.
- Add unit/integration tests that replay stored JSON samples from `docs/verification/` to avoid regressions without hitting live APIs during development.

## Deferred Workstreams
- Signal engine, execution/risk, watchdog, social distribution, dashboards, and cloud deployment remain paused until analytics outputs are signed off.
- Revisit the broader master plan only after the simplified pipeline (Environment → Alpha Vantage → IBKR → Analytics) is demonstrably stable.

## Operating Rhythm
- Before every new feature, confirm prerequisites: environment active, `.env` populated, requirements updated, verification docs ready.
- Capture blockers and open questions in `docs/notes.md` so nothing advances without clear inputs.
- Keep dependency changes tiny; prefer standard library solutions until a library is proven necessary.
