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

## Phase 2 – Alpha Vantage Ingestion (Sequential Iterations) ✅ Completed September 2025
- Delivered endpoints now cover the full Alpha Vantage surface we scoped: realtime options, intraday base feed, top gainers/losers, news sentiment, macro series (`REAL_GDP`, `CPI`, `INFLATION`, `TREASURY_YIELD`, `FEDERAL_FUNDS_RATE`), and fundamentals (`EARNINGS_CALENDAR`, `EARNINGS_ESTIMATES`, `INCOME_STATEMENT`, `BALANCE_SHEET`, `CASH_FLOW`, `SHARES_OUTSTANDING`, `EARNINGS_CALL_TRANSCRIPT`). See `docs/alpha_vantage_endpoints.md` for status tracking and the live captures stored under `docs/verification/`.
- Key outputs: configuration in `config/alpha_vantage.yml`, thin endpoint modules delegating to the shared runner, Redis payloads `raw:alpha_vantage:*`, heartbeats `state:alpha_vantage:*`, and unit tests covering validators/storage. CSV handling for calendar responses and the revised validator shapes are exercised in the test suite.
- Every endpoint has an updated sample fixture and a 2025-09-26 verification artifact; the tracker marks all entries `done` with notes on cadence, TTL, and payload structure.
- **Future Alpha Vantage endpoints – workflow reminder**
  - Adopt a strict one-endpoint-at-a-time workflow. Before coding, collect from the user: endpoint name, symbols/series, exact query parameters, sample JSON/cURL, expected cadence, and Redis TTL.
  - Log every request in `docs/alpha_vantage_endpoints.md` (awaiting-params → done).
  - For each iteration:
    1. Capture configuration in `config/alpha_vantage.yml` under a unique key.
    2. Keep the endpoint module thin; delegate execution to `AlphaVantageIngestionRunner` in `src/ingestion/alpha_vantage/_shared.py` (retries, Redis writes, heartbeats).
    3. Persist payloads to `raw:alpha_vantage:<endpoint>[:<symbol>]` with metadata (`requested_at`, `ttl_applied`, `request_params`).
    4. Validate manually, capture verification artefact in `docs/verification/<endpoint>_<date>.json`.
    5. Advance only after user sign-off on correctness, storage layout, and expiry behaviour.

## Phase 3 – Interactive Brokers Connectivity ✅ Completed September 2025
- Streams implemented and verified (paper TWS 127.0.0.1:7497):
  * Top-of-book quotes (`src/ingestion/ibkr/quotes.py` → `raw:ibkr:quotes:{symbol}`)
  * Level-2 depth rotation (`src/ingestion/ibkr/level2.py` → `raw:ibkr:l2:{symbol}`)
  * Account bundle (`src/ingestion/ibkr/account.py` → summary, positions, account/per-position PnL)
  * Execution stream (`src/ingestion/ibkr/executions.py` → `stream:ibkr:executions` + snapshot)
- Configuration lives in `config/ibkr.yml`; stream tracker (`docs/ibkr_streams.md`) lists all as `done` with verification artifacts.
- Each module includes async event handling, Redis persistence, heartbeats, and unit tests.
- **Future IBKR feeds – checklist**
  - Capture handshake inputs (account codes, cadence/TTL expectations, Redis contract) in `config/ibkr.yml` before coding. Update `docs/ibkr_streams.md` with status transitions.
  - Reuse the ib_insync connection helpers and emit heartbeats under `state:ibkr:*`.
  - Persist raw data under `raw:ibkr:*` (or stream namespaces) with consistent metadata; verify and archive snapshots in `docs/verification/` prior to advancing.

## Phase 4 – Analytics Foundations (After AV + IBKR Data Stable)
- All ingestion prerequisites are now met; Redis contains verified AV macro/fundamental keys alongside IBKR streams. Phase 4 can begin as soon as analytics scope is confirmed.
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
