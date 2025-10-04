# Phase 1 Implementation Guide – Unusual Whales Ingestion

## 1. Objective & Scope Alignment
- Deliver the Unusual Whales ingestion layer defined in project_scope.md (sections 5.1 & 13) and agents.md (Ingestion Service responsibilities).
- Provide live and historical data capture for SPY, QQQ, and IWM across WebSocket firehoses and high-value REST endpoints, enabling downstream analytics, risk, and execution modules in later phases.
- Establish rate-safe scheduling, persistence, and observability patterns that remain compatible with the Phase 0 toolchain (Makefile, Docker stack, FastAPI service skeleton).

## 2. Prerequisites & Environment Baseline
- API token: stored in `.env` (`UNUSUAL_WHALES_API_TOKEN`). Advanced tier confirmed, so all documented WebSocket channels and REST endpoints are available.
- Runtime: Python 3.11 environment per docs/runtime_environment.md with `asyncio`, `httpx`, `websockets`, `polars`, `pydantic`, `psycopg` and redis/postgres client libraries. Update `requirements.in` as new dependencies are introduced.
- Infrastructure: Docker-compose stack (FastAPI app + Redis + Postgres). Local Postgres must support partitioning extensions (native declarative partitioning suffices).
- Secrets management: `.env` remains git-ignored; any staging/prod variants will load via environment overrides.

## 3. Service Architecture Overview
- **Ingestion Service Package (`src/ingestion/` suggested)**
  - `websocket_consumer.py`: manages persistent connections, channel joins, reconnection strategy, and dispatching to channel-specific handlers.
  - `rest_scheduler.py`: orchestrates REST jobs with shared token bucket and per-job cadence definitions.
  - `serializers/`: Pydantic models that normalize live payloads (WebSocket + REST) and retain raw JSON for drift checks.
  - `publishers/redis.py`: upserts latest snapshots (`HSET`), appends to streams (`XADD`), and emits pub/sub notifications.
  - `persistence/postgres.py`: persists WebSocket events and archives REST payloads with deduplication guards.
  - `rate_limit.py`: global token bucket (120 calls/min) with metrics exposure and per-job budgeting.
  - `config.py`: pydantic settings to tune cadences, shard counts, and graceful degrade thresholds without code edits.
- Service hosted as an `asyncio` application. We will run it as a dedicated worker process (separate container/entrypoint in docker-compose) so the FastAPI service stays responsive, restarts are isolated, and websocket event loops are not influenced by HTTP request lifecycles.

## 4. WebSocket Integration Plan
### 4.1 Connection Management
- Single wss endpoint: `wss://api.unusualwhales.com/socket?token=...`.
- Use resilient client (`websockets` library) with heartbeat handling (`ping_interval=20s`, manual `pong`).
- Support multi-channel join per connection; maintain channel registry and replay pending joins on reconnect.
- Exponential backoff (5s → 60s) on disconnect, with jitter and cap at 5 attempts before raising alert.
- Detect silent failures via inactivity timer (no messages for 15s during market hours triggers reconnect).

### 4.2 Channel Workflows
- **Flow Alerts (`flow-alerts`)**
  - Deserialize into structured model including rule metadata, aggregated premiums, trade IDs.
  - Publish to Redis stream `uw:flow_alerts` capped at 10k entries with trimming and to hash `latest:uw:flow_alert:<ticker>`.
  - Persist to table `uw_flow_alerts` with unique `alert_id` constraint; store trade IDs array and raw JSONB.
  - Trigger REST follow-ups: queue `/api/option-contract/{id}/flow` for each option chain (with dedupe).
- **Option Trades (`option_trades`, `option_trades:<ticker>`)**
  - Maintain two connections: full tape filtered for target tickers (SPY/QQQ/IWM) and optionally aggregated for future expansion.
  - Buffer messages by ticker, flush every 1,000 trades or 2 seconds to Postgres via COPY, keeping ingestion lag <500ms.
  - Track rolling net premium & volume metrics pushed to Redis `uw:option_trades:<ticker>` stream for analytics seeds.
- **GEX Channels**
  - `gex:<ticker>`: ingest aggregated exposures once per minute; store to `uw_gex_snapshot` and Redis hash `latest:uw:gex:<ticker>`.
  - `gex_strike:<ticker>` and `gex_strike_expiry:<ticker>`: maintain snapshot caches with `strike` primary key; push to Postgres tables `uw_gex_strike` / `uw_gex_strike_expiry` using upsert-on-timestamp semantics.
- **Price (`price:<ticker>`)**
  - Collect 1-second updates; feed into in-memory OHLC builder that publishes 1m bars to Redis and table `uw_price_ticks` (optionally aggregated to `uw_price_bars` daily job).
  - Use as canonical source for realized volatility and syncing with REST metrics.
- **News (`news`)**
  - Stream into Redis pub/sub channel `uw:news` for AI commentator triggers.
  - Persist to `uw_news` table capturing timestamp, source, headline, ticker list, Trump flag.

### 4.3 Cross-cutting Concerns
- Message validation using generated schemas; unknown fields stored in JSONB but flagged via metrics.
- Backpressure: if Postgres writer lags (>2s), queue overflow to disk-based fallback (rotating ndjson) and alert.
- Idempotency: dedupe by `id` (option trades) / `alert_id` (flow alerts) / composite keys (ticker+timestamp+strike) before insert.

## 5. REST Ingestion Strategy
### 5.1 Scheduling Framework
- Shared limiter: 120 tokens/min (~2/s). Reserve 20% slack for ad-hoc lookups and retries.
- Define job tiers:
  - **Tier A (intraday-critical, 60s cadence)**: exposures, liquidity, premium ticks, NOPE, market tide.
  - **Tier B (5m cadence)**: strike/expiry breakdowns, net flow expiry, top net impact, options volume.
  - **Tier C (15m cadence)**: volatility statistics, realized/term, interpolated IV, IV rank.
  - **Tier D (daily/open/close)**: historical risk reversal skew, insider buy/sell, option chain snapshots, market calendars.
- Use `asyncio` scheduler with jitter (±10%) to avoid synchronized spikes.

### 5.2 Endpoint Catalog & Cadence
| Category | Endpoint | Cadence | Purpose |
|---|---|---|---|
| Spot Exposure | `/api/stock/{ticker}/spot-exposures` | 60s per ticker | Minute-level spot GEX exposure baseline for SPY/QQQ/IWM.
|  | `/spot-exposures/strike` | 5m staggered | Strike-level exposures for heatmaps; paginate with `limit=500`.
|  | `/spot-exposures/expiry-strike` | 5m alternating expiries | Joint strike/expiry exposures for positioning analytics.
| Greek Exposure | `/greek-exposure` | 5m | Aggregate gamma/charm/vanna totals.
|  | `/greek-exposure/strike` | 10m | Distribution by strike; sample high-interest strikes.
|  | `/greek-exposure/strike-expiry` | 10m | Align with term-structure analytics.
| Greek Flow | `/greek-flow` | 60s | Live delta/vega flows supporting institutional flow gauges.
|  | `/greek-flow/{expiry}` | 5m (nearest 4 expiries) | DTE-sensitive analytics.
| Volatility | `/volatility/realized` | 15m | Align realized vs implied vol updates.
### 5.1 Endpoint Catalog (Live)
All REST paths in Phase 1 are defined in `docs/api_queries.md` with a verified sample request. They fall into three groups:

**Ticker-scoped endpoints** (polled for every symbol in `target_tickers`, results archived in `uw_rest_payloads`):

| Endpoint | Default Cadence | Purpose |
| --- | --- | --- |
| `/api/darkpool/{ticker}` | 5m | Large off-exchange prints for signal overlays. |
| `/api/etfs/{ticker}/exposure` | 15m | ETF constituents/material exposures. |
| `/api/etfs/{ticker}/in-outflow` | 15m | Track ETF money flow. |
| `/api/market/{ticker}/etf-tide` | 10m | Options breadth per ETF. |
| `/api/stock/{ticker}/flow-alerts?limit=100` | 2m | REST mirror for WebSocket flow alerts (for reconciliation). |
| `/api/stock/{ticker}/flow-per-expiry` | 5m | Expiry-level flow aggregation. |
| `/api/stock/{ticker}/greek-exposure` (+ `/expiry`, `/strike`) | 5–10m | Spot/expiry/strike gamma footprints. |
| `/api/stock/{ticker}/greek-flow` | 5m | Delta/Vega flow aggregates. |
| `/api/stock/{ticker}/interpolated-iv` | 10m | Surface interpolation checkpoints. |
| `/api/stock/{ticker}/iv-rank` | 60m | Slow-moving IV percentile. |
| `/api/stock/{ticker}/max-pain` | 15m | Expiry-level max pain updates. |
| `/api/stock/{ticker}/net-prem-ticks` | 2m | Net premium bars for tape drift. |
| `/api/stock/{ticker}/nope` | 2m | Near-term NOPE metric. |
| `/api/stock/{ticker}/ohlc/1m?limit=500` | 2m | Continuity check against WebSocket prices. |
| `/api/stock/{ticker}/oi-change` | 5m | Intraday open-interest shocks. |
| `/api/stock/{ticker}/option-chains` | 15m | Chain metadata refresh. |
| `/api/stock/{ticker}/option/stock-price-levels` | 5m | Price-level stacking around underlying. |
| `/api/stock/{ticker}/options-volume` | 5m | Rolling volume/premium stats. |
| `/api/stock/{ticker}/spot-exposures` (+ `/strike`) | 5–10m | Spot/strike gamma snapshots. |
| `/api/stock/{ticker}/stock-state` | 5m | Quote/market status sanity check. |
| `/api/stock/{ticker}/stock-volume-price-levels` | 5m | Lit/off-lit depth. |
| `/api/stock/{ticker}/volatility/realized` | 10m | Realised vol time series. |
| `/api/stock/{ticker}/volatility/stats` | 10m | Summary IV/RV stats. |
| `/api/stock/{ticker}/volatility/term-structure` | 15m | IV term structure slice. |

**ETF & market-level endpoints (archived in `uw_rest_payloads`):**

| Endpoint | Cadence | Notes |
| --- | --- | --- |
| `/api/market/economic-calendar` | 24h (prefetch nightly) | Macro catalysts. |
| `/api/market/market-tide` | 5m | Systemic breadth indicator. |
| `/api/market/oi-change` | 15m | Market-wide OI shifts. |
| `/api/market/top-net-impact` | 5m | Leaders/laggards for dashboards. |
| `/api/market/total-options-volume?limit=100` | 5m | Baseline for normalization. |
| `/api/net-flow/expiry` | 15m | Expiry-level net flow baseline. |

### 5.2 Execution Model
- `RestScheduler` walks the catalog above, generating a request per ticker (or global scope) using builders in `rest/jobs.py`.
- Each response is stored verbatim (alongside request context) in Postgres for replay/audit. Deduplication uses a SHA-256 hash of the canonical JSON so repeated payloads update `fetched_at` without bloating storage.
- Cadences default to the values in `IngestionSettings.rest_job_cadences` and may be tuned per environment via `.env` overrides.
- `docs/api_queries.md` remains the source of truth for request examples and golden payloads; expanding ingestion requires updating that document and regenerating job definitions as needed.

### 5.3 Call Budget Estimate
- 1–2 minute tier (flow alerts mirror, NOPE, net-prem ticks, OHLC) → ~12 calls/min for three tickers.
- 5 minute tier (spot exposures, price levels, options volume, ETF tide, max pain, greek exposure) → ~21 calls every 5 minutes ≈ 4 calls/min.
- 10–15 minute tier (volatility stats, IV rank, economic calendar refresh) → ≈ 6 calls/min averaged.
- Market/global endpoints add ≈ 2 calls/min.
- Total steady state ≈ 24–26 calls/min, leaving >50% headroom for retries and burst on-demand lookups.

### 5.4 Data Freshness Goals
- Sub-minute metrics (NOPE, net premium ticks, flow alert mirror) delivered <60 s behind source.
- Exposure/greeks snapshots <5 minutes end-to-end.
- Calendars prefetched nightly and refreshed by 06:00 ET.

## 6. Persistent Storage Design (Draft for Review)
> Schemas will be finalized via migrations after review.

### 6.1 Postgres Tables (Core)
- `uw_flow_alerts` — `alert_id` PK with ticker, event timestamp, directional metadata, trade_ids array, `raw_payload`, `created_at`. Indexed on `(ticker, event_timestamp DESC)`.
- `uw_option_trades` — buffered WebSocket tape (`trade_id` PK) storing ticker, option symbol, event timestamp, price/size/premium, routing fields, `raw_payload`, `created_at` with `(ticker, event_timestamp DESC)` index.
- `uw_gex_snapshot`, `uw_gex_strike`, `uw_gex_strike_expiry` — WebSocket gamma exposure snapshots keyed by `(ticker, timestamp[,+ strike/expiry])` retaining raw JSON for drift audits.
- `uw_price_ticks` — canonical tick store keyed by `(ticker, event_timestamp)` with bid/ask snapshots.
- `uw_news` — streaming headlines (`headline_id` PK) with source metadata and ticker arrays.
- **New:** `uw_rest_payloads` — archival table capturing every REST response as JSONB with deduplicated hash (see §6.2).

### 6.2 REST Payload Archive
- Columns: `endpoint`, `scope`, `payload_hash`, `payload`, `fetched_at`.
- Primary key `(endpoint, scope, payload_hash)` ensures identical payloads simply refresh `fetched_at`.
- `payload` stores `{"response": <source JSON>, "context": {…request metadata…}}` so downstream tooling can replay requests exactly as received.
- Access patterns: latest snapshot per `(endpoint, scope)` via `ORDER BY fetched_at DESC`, or change detection by comparing hashes.

### 6.3 Retention & Maintenance
- WebSocket history (ticks, trades, flow alerts, GEX) retains two years with monthly pruning jobs.
- `uw_rest_payloads` keeps 90 days hot by default; archival/export to S3/Snowflake handled in Phase 2 once analytics consumers are defined.
- Nightly job (Phase 2) will roll high-volume Redis state into Postgres or S3, but Phase 1 focuses on live capture + raw REST archives described above.

## 7. Redis Data Contracts
- Hash `latest:uw:flow_alert:<ticker>`: last alert payload (no TTL; always reflects latest state).
- Stream `uw:flow_alerts`: full alert events capped at ~10k entries (≈1–2h of data) using `XTRIM MINID` to keep memory bounded while preserving enough context for analytics.
- Hash `latest:uw:gex:<ticker>`, `latest:uw:gex_strike:<ticker>:<strike>`, `latest:uw:gex_strike_expiry:<ticker>:<expiry>` (no TTL, single-snapshot semantics).
- Stream `uw:option_trades:<ticker>`: raw trade events with `MAXLEN ~ 10000` per ticker; downstream analytics consume via dedicated groups.
- Hash `latest:uw:price:<ticker>` & `uw:price_bar_1m:<ticker>`: most recent tick and 1m bar snapshots (no TTL).
- Pub/Sub `uw:news` for AI commentator and dashboards.
- Global keys `ingestion:health:*` for heartbeat, backlog metrics, and last success timestamps.

## 8. Rate Limiting & Backpressure Controls
- Global limiter seeded at 120 tokens/min with 90-token floor for scheduled jobs; 24 tokens reserved for bursts.
- Endpoint groups get per-cadence quotas; scheduler monitors consumption and defers low-priority jobs if usage exceeds 90% of window.
- Retry logic: HTTP 429 → exponential backoff starting 10s; network errors → quick retry (3 attempts) then escalate.
- Postgres queue depth monitoring: if outstanding batches >5 per table, throttle REST pulls and drop WebSocket enrichment tasks to fail-safe mode. Optional disk spooling of overflow payloads is implemented but disabled by default; enable only if stability issues arise.

## 9. Observability & Alerting
- **Metrics exporter (outstanding):** FastAPI `/metrics` should expose websocket connectivity, message rates, REST latency, limiter tokens remaining, Postgres insert latency, and Redis publish lag. Wiring remains a follow-up task for Phase 1 close-out.
- Structured JSON logs (stdout) with trace IDs linking WebSocket receipt → Redis publish → Postgres insert; this is the primary monitoring surface for now.
- Alerts (Phase 1): rely on log inspection and ad-hoc checks; Prometheus/Alertmanager integration remains a Phase 3 task.
- Dead letter queue support exists for future use, but remains disabled unless we decide to spool overflow payloads.

## 10. Testing & Validation Strategy
### 10.1 Contract Fidelity
- Generated Pydantic models mirror the OpenAPI schema so every documented field is represented. Unknown fields fall back to JSONB capture and are logged as drift events.
- Each channel/endpoint stores the raw payload in Postgres (`raw_payload` JSONB) and/or Redis hashes. Automated diff checks compare the inbound JSON to the structured columns to confirm no key loss.

### 10.2 Automated Verification Pipeline
- **Unit tests:**
  - WebSocket handlers: inject fixture payloads and assert both the Redis message and the Postgres insert payload round-trip identical JSON keys/values.
  - REST adapters: mock `httpx` responses using official sample payloads; assert serializer output and persistence layer preserve every field.
- **Golden sample suite:** for each REST endpoint and WebSocket channel, capture canonical payloads from live calls (scrub identifiers) and store under `tests/data/uw/<endpoint>.json`. Integration tests replay the payload, write to Postgres/Redis, then read back and compare hashes/field lists.

### 10.3 Live Integration Checks
- **Ingress→Storage checksum:** store a SHA256 of the canonical JSON on reception; a scheduled verification task re-reads the most recent Postgres row and Redis hash, re-computes the hash, and alerts on mismatch.
- **Schema coverage metrics:** nightly job enumerates JSON keys present in the last 24h per endpoint and compares against the OpenAPI schema; missing keys trigger warnings for review.
- **Sampling queries:** `make ingest-verify` runs SQL scripts that pull the latest N records per table, dumping to ndjson for manual spot checks and Git-tracked diffs.

### 10.4 Rate-Limited End-to-End Tests
- Manual test harness (invoked off-hours) connects to WebSockets and executes selected REST calls end-to-end, then asserts: message persisted (row count increment), Redis key updated, and checksum matches.
- Replay harness can feed recorded payloads back through the persistence pipeline to validate migrations or schema updates without calling the live API.

### 10.5 Drift Detection
- Daily cron downloads the latest OpenAPI spec, hashes it, and breaks the build if it changes without regenerated models.
- Redis and Postgres field validators log any unexpected null coercions or type casts, enabling quick diagnosis of upstream schema shifts.

## 11. Deployment & Operations Checklist
- Update `requirements.in`, run `pip-compile`, regenerate `docs/runtime_versions.txt`.
- Extend Dockerfile/compose to include ingestion worker if run separately; ensure healthchecks for Redis/Postgres dependencies.
- Add Make targets: `make ingest-run`, `make ingest-test`, `make ingest-replay`.
- Document environment variables: Redis DSN, Postgres DSN, limiter overrides (`UW_RATE_LIMIT`), feature flags (enable/disable endpoints).
- Provide runbook excerpt covering start/stop commands, log locations, and verifying data ingestion (SQL sample queries, Redis CLI checks).

## 12. Outstanding Tasks & Phase 1 Follow-ups
- Phase 1 remains open until the items below are closed.
- Wire the ingestion metrics exporter (`/metrics`) so Phase 1 exposes token bucket state, queue depth, and persistence lag.
- Classify each REST/WebSocket feed as “Redis snapshot”, “Postgres archive”, or “needs transformation”, then iterate through the list (Phase 2) to build curated tables.
- Keep `docs/api_queries.md` in sync with any new endpoints or payload shape changes gathered from production.
- Derive analytics-friendly Postgres tables from `uw_rest_payloads` once downstream consumers request them (Phase 2 scope).

## 13. Implementation Phasing
We will follow the week-by-week milestones below; no additional management cadence is required beyond these checkpoints.
1. **Week 1:** Generate client models, build WebSocket scaffolding, set up Redis contracts, implement Flow Alerts + Price channel persistence.
2. **Week 2:** Add Option Trades + GEX channels, finalize Postgres schema migrations, establish rate limiter foundation.
3. **Week 3:** Implement REST scheduler Tier A/B endpoints, integrate persistence & metrics, start integration testing.
4. **Week 4:** Layer Tier C/D endpoints (including calendars), tune cadences, write documentation/runbook updates, obtain schema approval.

## 13. Approvals & Open Questions
- Confirm Postgres schema outlines above or request adjustments before migrations are scripted.
- Validate proposed cadences satisfy analytic needs while respecting rate limits (feedback welcome before coding).
- Decide whether ingestion worker runs as part of FastAPI app or dedicated process.
- Determine archive strategy for disk spools (if used) and S3/offsite backups (Phase 2 consideration).

## 14. Next Actions for Review
- Review this document for cadence acceptance, schema design, and operational approach.
- Once approved, we will:
  1. Author migrations and code scaffolding.
  2. Update docs/agents.md to reflect active WebSocket & REST responsibilities as implementation begins.
  3. Begin incremental development following the schedule above.
