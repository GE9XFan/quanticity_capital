# Unusual Whales Integration Blueprint

## 1. Purpose & Goals
- Build the Unusual Whales (UW) ingestion and analytics stack to institutional-grade quality using the full REST catalogue and high-volume websocket streams.
- Unify UW data with the Interactive Brokers (IBKR) feeds to deliver real-time market microstructure, dealer positioning, and options flow analytics for trading, risk, and research teams.
- Replace the existing `uw_ingestion` module, scripts, and docs with a modular architecture that scales to millions of events per day, enforces 120 RPM API limits, and supports advanced analytics workloads.

## 1.1 Operational Simplicity Guardrails
- Maintain the existing `Redis` + `PostgreSQL` toolchain as the default; defer Kafka/Iceberg until scale or retention requirements force the upgrade.
- Keep deployment footprint small: begin with a single ingestion service (REST + websockets) and a lightweight processing worker; reintroduce analytics without expanding infrastructure unnecessarily.
- Treat advanced components (Kafka, schema registry, distributed tracing) as optional backlog items; provide clear runbooks before introducing them.
- Preserve the repo’s “one engineer can operate it” philosophy by documenting workflows, automating smoke tests, and keeping infrastructure-as-code minimal.

## 2. Implementation Status (Updated October 2025)

### 2.1 Completed Components

| Component | Path | Status | Details |
|---|---|---|---|
| **Core Clients** | `src/quanticity_capital/unusual_whales/clients.py` | ✅ Complete | AsyncUWRestClient with rate limiting (TokenBucketLimiter), UWWebsocketClient with automatic reconnect |
| **REST Ingestion** | `src/quanticity_capital/unusual_whales/rest.py` | ✅ Complete | RESTIngestionWorker & RESTIngestionService with priority-based scheduling, 42 configured endpoints across 4 tiers |
| **WebSocket Ingestion** | `src/quanticity_capital/unusual_whales/ws.py` | ✅ Complete | WebsocketIngestionWorker & WebsocketIngestionService supporting 6 validated channels |
| **Orchestrator** | `src/quanticity_capital/unusual_whales/orchestrator.py` | ✅ Complete | UnusualWhalesOrchestrator coordinating REST/WS lifecycle, rate limiting, and graceful shutdown |
| **Persistence Layer** | `src/quanticity_capital/unusual_whales/persistence.py` | ✅ Complete | RedisPersistence with stream-based buffering, daily snapshots, and latest-value caching |
| **REST Models** | `src/quanticity_capital/unusual_whales/rest_models.py` | ✅ Complete | 84 Pydantic models covering all 42 REST endpoints with validation |
| **WebSocket Models** | `src/quanticity_capital/unusual_whales/ws_models.py` | ✅ Complete | 8 validated models (flow-alerts, news, option_trades, gex, gex_strike, gex_strike_expiry) |
| **Logging** | `src/quanticity_capital/unusual_whales/logging.py` | ✅ Complete | Structured logging with contextual enrichment (endpoint, symbol, tier, channel) |
| **Metrics** | `src/quanticity_capital/unusual_whales/metrics.py` | ✅ Complete | Prometheus metrics for REST/WS operations, rate limiting, persistence |
| **Configuration** | `src/quanticity_capital/unusual_whales/settings.py`<br>`config/unusual_whales.yaml` | ✅ Complete | Feature flags, multi-tier cadence system, symbol watchlists, rate limits (120 RPM) |
| **Test Suite** | `tests/test_unusual_whales_*.py` | ✅ Complete | 10 test files (3,305 lines) covering unit tests, integration tests, model validation |

### 2.2 REST Endpoints (42 Configured)
**Tier 0 (30s cadence):** greek-flow, spot-exposures, net-prem-ticks, options-volume
**Tier 1 (5min cadence):** flow-per-expiry, flow-per-strike, flow-per-strike-intraday, oi-change, spot-exposures-strike, stock-state, ohlc-1m, flow-recent, greeks, nope, flow-alerts
**Tier 2 (1hr cadence):** greek-exposure, greek-exposure-expiry, greek-exposure-strike, volume-oi-expiry, max-pain, oi-per-expiry, oi-per-strike, interpolated-iv, iv-rank, volatility-realized, volatility-stats, volatility-term-structure, historical-risk-reversal-skew, stock-volume-price-levels, analysts, insider-buy-sells
**Tier 3 (daily cadence):** expiry-breakdown, option-contracts, atm-chains, option-chains, stock-price-levels, spot-exposures-expiry-strike, flow-alerts-global

### 2.3 WebSocket Channels (6 Enabled, 7 Total)
- **flow-alerts:** Proprietary unusual flow alerts
- **news:** Live headline feed
- **option_trades:** Raw options tape (global + ticker-scoped)
- **gex:TICKER:** Dealer gamma exposure by ticker
- **gex_strike:TICKER:** Gamma exposure by strike
- **gex_strike_expiry:TICKER:** Gamma exposure by strike and expiry

*Note: The price channel is supported but currently disabled in configuration. The lit_trades and off_lit_trades channels are enterprise-only features not available on Advanced plan.*

### 2.4 Architecture Highlights
- **Rate Limiting:** Token bucket implementation enforcing 120 RPM with configurable burst, priority-based request routing
- **Persistence:** Redis Streams for message buffering, daily snapshots (hashes), latest values (keys with TTL)
- **Observability:** Structured JSON logging, Prometheus metrics for requests, messages, errors, latency
- **Resilience:** Automatic reconnection, jittered backoff, circuit breaker patterns, graceful degradation
- **Configuration:** Feature flags for REST/WS enable/disable, per-endpoint/channel toggles, symbol watchlists (tier0/tier1/tier2)

### 2.5 Pending Work
| Component | Status | Priority |
|---|---|---|
| Analytics Engine | Not Started | Next Phase |
| PostgreSQL/Timescale Integration | Not Started | Medium |
| S3/Parquet Cold Storage | Not Started | Low |
| Kafka Migration Path | Not Started | Low |
| Production Deployment | Pending | High |

## 3. Target Architecture Overview
```
             +----------------------+         +-----------------------+
             |  Scheduler & Orches. |<------->|  Config & Feature Tog |
             +----------+-----------+         +-----------+-----------+
                        |                                 |
        +---------------+---------------+                 |
        |                               |                 |
+-------v--------+             +--------v-------+         |
| REST Ingestion |             | Websocket Ings |         |
| (async workers)|             | (stream client)|         |
+-------+--------+             +--------+-------+         |
        |                               |                 |
        +---------------+---------------+                 |
                        |                                 |
                +-------v-------+                 +-------v-------+
                | Stream Buffer |                 |  KV Cache     |
                | (Kafka/Redis) |                 | (Redis)       |
                +-------+-------+                 +-------+-------+
                        |                                 |
        +---------------+---------------+                 |
        |                               |                 |
+-------v--------+             +--------v-------+         |
|  Data Lake /   |             |  Real-time     |         |
|  Warehouse     |             |  Analytics     |<--------+
|  (Iceberg/S3)  |             |  Engine        |
+-------+--------+             +--------+-------+
        |                               |
        +---------------+---------------+
                        |
                +-------v-------+
                | Downstream    |
                | Clients (OMS, |
                | dashboards)   |
                +---------------+
```

Key tenets:
1. Separate acquisition (REST vs websocket) from transport, storage, and analytics.
2. Use resilient stream buffers (Redis Streams today, upgrade path to Kafka/NATS) to decouple producers and consumers.
3. Persist raw + enriched datasets in the existing Redis/Postgres stores by default, adding S3/Parquet (and eventually Iceberg) only when retention or replay needs demand it.
4. Feed the analytics engine with normalized UW data alongside IBKR inputs to unlock joint models (e.g., hedging pressure vs book imbalance).

## 4. Data Acquisition Design

### 4.1 REST Endpoint Strategy
- **Cadence Bands**
  - *Tier 0 (Critical Intraday, <=30s cadence):* `greek-flow`, `spot-exposures`, `net-prem-ticks`, `options-volume` snapshots for top watchlist tickers.
  - *Tier 1 (High Intraday, 1-5 min):* `flow-per-expiry`, `flow-per-strike(-intraday)`, `oi-change`, `spot-exposures/strike`, `stock-state`, `ohlc/1m`.
  - *Tier 2 (Daily/End-of-day):* `greek-exposure(/{expiry,strike})`, `volume-oi-expiry`, `volatility/*`, `max-pain`, `oi-per-*`, `analysts`, `insider-buy-sells`.
  - *Tier 3 (On-demand / Research):* `option-contract/{id}/*`, `option-contracts`, `atm-chains`, `option/stock-price-levels`, etc.
- **Request Orchestration**
  - Config-driven schedules stored in `config/data_sources.yaml` (or new `config/unusual_whales.yaml`).
  - Async worker pool (Python `asyncio` + `httpx`) with token bucket per credential to honor 120 RPM (rate=2/s, burst configurable).
  - Priority routing ensures Tier 0 > Tier 1 > Tier 2 > Tier 3 when rate-limited.
- **Response Handling**
  - Validate JSON schemas per endpoint; log anomalies to structured logging and metrics.
  - Normalize payloads to canonical schemas (e.g., `uw.greeks.flow`, `uw.flow.expiry`).
  - Enrich with metadata (ingest timestamp, source, ticker, expiry) before publishing to stream buffer.

### 4.2 Websocket Strategy
| Channel | Purpose | Notes |
|---|---|---|
| `option_trades` (global + ticker-scoped) | Raw options tape (~6-10M/day) | Requires sharding workers, compression, optional on-the-fly filtering (watchlist, premium thresholds). |
| `flow-alerts` | Proprietary unusual flow alerts | Low volume, high signal; persist alert audit trail. |
| `gex:*` suite | Dealer hedging metrics (ticker/strike/expiry) | Align sampling frequency with hedging dashboard; aggregate to 1s/15s intervals post-ingest. |
| `price:TICKER` | Equity price stream | Use to align options flow with price moves. |
| `news` | Headline feed | Route to event processing module for sentiment tagging. |

Implementation details:
- Start with a single asyncio service hosting both REST polling tasks and websocket listeners; split into separate deployables only if CPU or latency warrants it.
- Leverage `websockets` or `aiohttp` with automatic reconnect, jittered backoff, and heartbeats.
- Partition websocket consumers by channel group only when scale tests demonstrate the need (e.g., move `option_trades` to a dedicated worker later).
- Immediately batch and publish incoming payloads to Redis Streams; predefine Kafka topic names only for future cutover.
- Keep lightweight in-memory caches only for deduplication/windowing (e.g., track `trade_id` to avoid replays).

## 5. Data Processing & Persistence

### 5.1 Stream Buffer Layer
- **Primary:** Redis Streams (existing infra) with per-channel streams such as `uw:raw:option_trades`, `uw:raw:gex:ticker`, `uw:rest:greek_flow`.
- **Upgrade Path:** Kafka/NATS for ordered, durable replay once infra is ready; keep this on the roadmap but do not deploy until message volume dictates.
- **Schema Registry (optional):** Maintain JSON schema definitions in-repo; graduate to a registry service only if/when Kafka is adopted.

### 5.2 Storage
- **Hot Cache:** Redis hashes/Sorted Sets for last-known state (e.g., latest `spot-exposures`, rolling `net-prem-ticks`).
- **Warm Store:** PostgreSQL or Timescale for aggregated metrics (e.g., minute bars, expiry summaries) to power dashboards.
- **Cold Store/Data Lake (optional):** When longer retention is required, batch-write Parquet to S3 (partitioned by `date/ticker/channel`). Evaluate Apache Iceberg only if complex rewind workflows justify the overhead.
- **Backfill:** Introduce daily job hitting `/api/option-trades/full-tape` to backfill prior day trades directly to lake.

### 5.3 Processing Pipelines
- Build modular consumers within the forthcoming analytics service (light-weight async workers) that:
  1. Consume raw UW streams.
  2. Apply normalization & quality checks.
  3. Join with IBKR data where needed (e.g., price alignment, depth-of-book context).
  4. Publish enriched metrics to `analytics:*` streams/keys.
- Maintain sliding windows for calculations (e.g., 1h net premium, top strikes by GEX, vol term structure deltas) using Redis sorted sets; scale out with pandas-on-Ray only if simple aggregations prove insufficient.

## 6. Analytics & Product Deliverables
- **Dealer Positioning Dashboard:** Combine `gex` websocket feeds with `spot-exposures` REST to track gamma flip zones and vanna cliffs in real-time.
- **Flow Heatmaps:** Use `flow-per-strike(-intraday)` + websocket trades to visualize strike/expiry pressure.
- **Volatility Suite:** Integrate `interpolated-iv`, `volatility/stats`, `risk-reversal`, `realized-volatility` into term-structure monitors; compare against IBKR implieds.
- **Flow Scoring Engine:** Merge `flow-alerts`, `option_trades`, and `oi-change` to score unusual activity, factoring premium size, OI ratio, follow-through.
- **Event-driven Alerts:** Trigger notifications when news events coincide with large GEX shifts or flow alerts (requires rules engine).

## 7. Security, Reliability, Observability
- Store UW tokens in secret manager (`.env` -> Vault/KMS). Rotate quarterly.
- Implement circuit breakers: stop lower-priority polling when rate-limit breaches occur.
- Observability stack: continue with structured logs (JSON) and Prometheus metrics (`uw_requests_total`, `uw_ws_messages`, `uw_rate_limit_hits`); leave distributed tracing as an enhancement once we add more services.
- Backpressure handling: queue depth alerts, drop strategies for non-critical channels if throughput threatened.
- Disaster recovery: daily snapshots of Redis Streams; add S3 replication once cold storage is enabled.

## 8. Migration & Decommission Plan
1. **Design & Scaffold (Week 1-2)**
   - Finalize schemas, config model, and orchestration layout.
   - Build new package namespace (`src/quanticity_capital/unusual_whales/`).
2. **Implement Acquisition Layer (Week 2-4)**
   - REST + websocket services publishing to new streams.
   - Smoke tests with sandbox tickers.
3. **Processing & Analytics Integration (Week 4-6)**
   - Begin designing the replacement analytics service in parallel, defining output contracts for downstream layers.
   - Introduce feature flags to switch from legacy feeds to new ones per dataset.
4. **Parallel Validation (Week 6-7)**
   - Replay recorded UW samples or run a short-lived branch of the legacy code (if needed) to benchmark output parity.
5. **Cutover (Week 8)**
   - Flip feature flags to use new feeds.
   - Freeze any temporary legacy branches.
6. **Decommission (Week 9, completed Oct 2025)**
   - Removed `src/quanticity_capital/uw_ingestion`, legacy scripts, and obsolete docs.
   - Updated architecture docs and README references.
   - Archive final legacy data snapshots.

## 9. Immediate Next Steps
- Approve architectural blueprint and identify any additional requirements (e.g., compliance logging, integration with OMS).
- Decide on stream buffer target (Redis-only vs Kafka roadmap) to inform implementation choices now.
- Implement configuration schema and ingestion scaffolding (see `config/unusual_whales.yaml` and `src/quanticity_capital/unusual_whales/`).
- Enumerate priority tickers/universes for Tier 0/1 polling and websocket filtering.
- Draft the scope/output contracts for the post-rebuild analytics engine so downstream consumers stay aligned.
- Stand up project board tracking the migration phases above.

Once confirmed, we can start scaffolding the new module and drafting the config + schema definitions.
