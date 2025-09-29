# Quantum Trading System – Sequential Architecture Blueprint

## 0. Guiding Principles
- **Module-first delivery**: finish each module end-to-end (code, config, tests, dashboards, docs) before moving on. No partial features or MVP shortcuts.
- **Python 3.11 baseline**: enforce type hints, asyncio support, and compatibility with uvloop/numba when available.
- **Direct control of market data**: integrate AlphaVantage via native REST, own the protocol, and deprecate legacy wrappers.
- **Performance-conscious by default**: maintain sub-150 ms path from ingestion → storage → analytics for priority symbols; prefer async I/O, batching, and vectorized math to serialized loops.
- **Observability everywhere**: Docker Compose provisions Prometheus/Grafana plus Redis metrics from day one; every module exposes metrics and alert hooks.
- **Live endpoint testing**: integration suites hit real AlphaVantage and IBKR (paper) endpoints under strict budgets, with telemetry visible in Grafana.
- **Cloud-ready**: design artifacts so the stack ports cleanly to GCP (GKE + Redis Stack), including secrets management, monitoring, and persistent storage.
- **Commercial delivery built-in**: social and premium distribution channels (Discord, Telegram, Twitter, email) are first-class modules, not afterthoughts.

---

## 1. Module 0 – Environment & Observability Foundation
**Dependencies**: none

### Scope
Establish the runnable platform on a single developer workstation with Docker Compose as the backbone, providing runtime containers, configuration management, and baseline observability (metrics + alerting).

### Deliverables
- Repository structure aligned with module breakdown (`environment/`, `data_ingestion/`, `ibkr/`, `analytics/`, `signals/`, `execution/`, `reporting/`, `ai_overseer/`, `social/`, `deployment/`).
- `docker-compose.yml` orchestrating:
  - `app` (Python 3.11 image with project code mounted for dev).
  - `redis-stack` (Redis TimeSeries enabled).
  - `prometheus` scraping the app and redis-exporter sidecar.
  - `grafana` with provisioned dashboards.
  - Optional `ibkr-gateway` container stub or SSH tunnel placeholder (activated later).
- `.env` template, `config/system.yaml`, and credentials templates (`config/credentials.yaml.example`).
- Makefile/Taskfile commands: `make up`, `make down`, `make lint`, `make test`, `make profile`, `make dashboards-sync`.
- Grafana dashboards (JSON) for: **System Overview**, **Ingestion & Rate Limits**, **Test Telemetry**, **Redis Health**.
- Prometheus alert rules for ingestion failures, Redis latency, missing heartbeats.

### Implementation Notes
- Use multi-stage Dockerfile with `python:3.11-slim`, caching pip-tools compiled wheels.
- Mount `prometheus.yml` and alert rules via config volume; include scrape jobs for `app:9100` metrics endpoint and `redis-exporter:9121` (dedicated exporter container built from `oliver006/redis_exporter:v1.54.0` with `REDIS_ADDR=redis-stack:6379`).
- Provision Grafana via `provisioning/` directory to auto-import dashboards and configure data sources.
- Centralize configuration via Pydantic settings. Module-specific configs live under `config/modules/`.

### Testing & Observability
- Smoke test: `make test-smoke` spins stack, executes dummy ingestion task, verifies metrics appear in Grafana (dashboard panel shows ingestion latency under 100 ms).
- Prometheus metrics baseline: `system_module_up`, `config_reload_success_total`, `redis_connected{}`.

### Exit Criteria
- `docker compose up` brings up full stack with green health checks.
- Grafana accessible with dashboards populated after smoke test.
- Documentation (`docs/module0_environment.md`) describing services, ports, secrets, and troubleshooting.

---

## 2. Module 1 – AlphaVantage REST Ingestion & Storage
**Dependencies**: Module 0

### Scope
Build direct REST ingestion for AlphaVantage premium endpoints, enforce rate limits (600 calls/min), normalize responses, and store results in Redis TimeSeries + archival storage.

### Deliverables
- `data_ingestion/alphavantage_rest.py`: async client using `httpx.AsyncClient` with retry/backoff, HTTP/2, structured logging.
- `data_ingestion/rate_limiter.py`: Redis-backed token bucket keyed by AlphaVantage functions (`REALTIME_OPTIONS`, `HISTORICAL_OPTIONS`, `TIME_SERIES_INTRADAY`, core technical indicators, macro/fundamental endpoints).
- `data_ingestion/stream_scheduler.py`: orchestrates symbol buckets (0DTE, 1DTE, 14-45 DTE, macro series) and launches concurrent ingestion tasks (frequencies defined in `config/alpha_vantage.yaml`).
- `config/watchlists.yaml`: default watchlist covering `SPY`, `QQQ`, `IWM`, `SPX`, the Magnificent Seven (`AAPL`, `MSFT`, `GOOGL`, `AMZN`, `META`, `NVDA`, `TSLA`), plus `COST`, `WMT`, `DIS`, `V`, `NFLX`, `HOOD`, `HIMS`, `ORCL`; supports overrides per environment.
- `config/alpha_vantage.yaml`: scheduler configuration defining per-bucket endpoints, frequencies, params, and environment overrides.
- `data_ingestion/normalizer.py`: transforms payloads into DTOs (`OptionQuote`, `UnderlyingQuote`, `IndicatorSeries`).
- `storage/redis_timeseries.py`: bulk write helpers using `TS.MADD`, index management, retention policies, and compaction rules (1s→1m→5m) for hot vs warm layers.
- `storage/ingestion_index.py`: maintains symbol/expiry→Redis key mappings, latest timestamps, and data freshness flags for downstream modules.
- `storage/archive.py`: nightly Parquet export to local disk (S3/GCS ready) with metadata manifest and checksum validation (no additional JSON snapshots to minimize storage).
- Prometheus metrics: `alphavantage_calls_total{function=…}`, `alphavantage_latency_ms`, `alphavantage_throttle_events_total`, `redis_ts_write_ms`.
- Grafana dashboard panels for call rate vs quota, latency percentiles, and ingestion backlog depth.

### Implementation Notes
- Primary REST functions to support: `REALTIME_OPTIONS` (with `require_greeks=true` and optional `contract=` filters), `HISTORICAL_OPTIONS` (date-scoped backfills), `TIME_SERIES_INTRADAY` (using `outputsize=full` and `month/slice` parameters for deep history).
- Technical indicator coverage (configurable, default set): `SMA`, `EMA`, `WMA`, `DEMA`, `TEMA`, `WILLR`, `RSI`, `STOCH`, `STOCHF`, `MACD`, `BBANDS`, `ADX`, `CCI`, `MFI`, `MINUS_DI`/`PLUS_DI`, `OBV`, `AROON`, `VWAP`.
- Macro/fundamental endpoints to schedule: `REAL_GDP`, `REAL_GDP_PER_CAPITA`, `TREASURY_YIELD`, `FEDERAL_FUNDS_RATE`, `CPI`, `INFLATION`, `RETAIL_SALES`, `DURABLES`, `UNEMPLOYMENT`, `NONFARM_PAYROLL`, `NEWS_SENTIMENT` (note: `NEWS_SENTIMENT` excludes ETFs—omit for `SPY`, `QQQ`, `IWM`, `SPX`).
- Trading buckets:
  - **0DTE / 1DTE**: limited to `SPY`, `QQQ`, `IWM`, `SPX`; tradeable signals include intraday gamma scalping, regime shifts, and market-on-close imbalances.
  - **14-45 DTE**: applied to full equity watchlist (Magnificent Seven + `COST`, `WMT`, `DIS`, `V`, `NFLX`, `HOOD`, `HIMS`, `ORCL`).
- Market-on-close imbalance ingestion covers `SPY`, `QQQ`, `IWM`, `SPX` only; store imbalance metrics in Redis for signal module.
- Storage strategy:
  - **Hot path**: Redis TS series per underlying/contract/indicator (`options:{symbol}:{expiry}:{strike}:{right}`, `underlyings:{symbol}`, `indicators:{symbol}:{function}`) with 7-day retention and downsampling to 1m/5m summaries.
  - **Metadata**: Redis Hash/JSON entries capturing last update timestamps, data quality flags (`fresh`, `stale`, `partial`), and source attribution (AlphaVantage vs fallback).
  - **Cold archive**: Parquet partitioned by `symbol/date/function`, stored locally with checksum, upload hooks to cloud storage when Module 8 lands. Maintain manifest for replay/backtesting.
- Batch symbol requests, avoid sequential loops; use `asyncio.gather` with bounded semaphore.
- Cache last successful payload in Redis for failover; tag stale data in DTO metadata.

- Cadence matrix (keeps total calls ~70/min with >5x safety margin):
  | Category | Endpoint(s) | Symbols | Frequency | Calls/min | Notes |
  |---|---|---|---|---|---|
  | 0DTE/1DTE options | `REALTIME_OPTIONS` | SPY, QQQ, IWM, SPX | every 12 s | 20 | requires `require_greeks=true`; responses feed Greeks + signals |
  | 0DTE/1DTE underlyings | `TIME_SERIES_INTRADAY` (1m) | SPY, QQQ, IWM, SPX | every 60 s | 4 | 1‑minute bars for latency metrics |
  | Extended options | `REALTIME_OPTIONS` | Magnificent Seven + COST/WMT/DIS/V/NFLX/HOOD/HIMS/ORCL | every 45 s | 20 | bucket rotated but still <1.5 calls/min per symbol |
  | Extended underlyings | `TIME_SERIES_INTRADAY` (1m slice) | same as above | every 120 s | 7.5 | downsampled to 1m/5m cadences |
  | Technical indicators | indicator endpoints (listed above) | same as above | round‑robin; each symbol runs 1 indicator/min | 15 | indicators rotate so full set refreshes every ~10 min |
  | Macro + breadth | macro endpoints (`CPI`, `GDP`, etc.) | global | every 60 min | <0.2 | negligible footprint |
  | News sentiment | `NEWS_SENTIMENT` | non-ETF equities | every 10 min | 1.5 | skip ETFs per AV rules |
  | Backfills | `HISTORICAL_OPTIONS`, archival slices | selected | nightly | — | throttled via separate job outside hot path |
  The scheduler enforces a per-function semaphore of 8 QPS and global ceiling of 8 requests/s (480/min) leaving slack for retries and manual replays.

### Testing
- Unit tests with recorded fixtures for payload parsing.
- Live integration suite `pytest -m live_alpha`:
  - Gated by `ALPHA_VANTAGE_API_KEY` env var and `LIVE_ALPHA_TESTS=1`.
  - Executes limited set (<30 calls) verifying DTO integrity and Redis writes.
  - Emits Prometheus counters (`test_live_alpha_success_total`).
- Watch Grafana **Test Telemetry** panel during live runs to ensure rate budget compliance.

### Exit Criteria
- 24-hour live run without manual intervention; all ingestion metrics within target thresholds.
- Redis keys populated for configured watchlist; archival files generated.
- Runbook (`docs/module1_alpha_vantage.md`) covering endpoints, limits, recovery steps.

---

## 3. Module 2 – IBKR Market & Order Integration
**Dependencies**: Modules 0-1

### Scope
Integrate with TWS/Gateway over port 7497, ingest market data, capture account updates, and prepare order routing infrastructure with persistence.

### Deliverables
- `config/ibkr.yaml`: connection host/port (default `127.0.0.1:7497`), per-module client IDs (`101`, `201`, `301` to avoid clashes with default `1`), market data type, pacing budgets, symbol watchlists, and per-symbol depth exchanges.
- `ibkr/connection_manager.py`: manages async lifecycle (leveraging `ib_insync.IB`), heartbeats, auto-reconnect with Prometheus gauges (`ibkr_connection_state`, `ibkr_reconnects_total`).
- `ibkr/contracts.py`: contract factories for underlyings, option chains (SMART routing, penny vs nickel), and volatility surfaces.
- `ibkr/market_data.py`: subscribes to underlying top-of-book quotes, option chain L1 data, `tickOptionComputation` Greeks, tick-by-tick trades/bid-asks; normalizes to DTOs and publishes to ingestion bus.
- `ibkr/market_depth.py`: manages Level II depth subscriptions (`reqMktDepth`) for configured exchanges and aggregates depth snapshots for analytics with rotating subscription windows.
- `execution/order_router.py`: async interface exposing `submit(signal: SignalEnvelope) -> OrderAck` and `register_ack_listener(callback)`; Module 2 ships a stub returning queued acks, Module 5 swaps in live IBKR routing while keeping the contract unchanged (idempotency tokens, IBKR order refs, and pre-trade risk checks).
- `execution/position_store.py`: reconciles positions/fills with Redis snapshots and archival storage.
- `ibkr/bar_aggregator.py`: consumes tick-by-tick/5s data, aggregates into 1m/2m/5m bars per symbol, persists to Redis TS (`ibkr:bars:{symbol}:{interval}`) for analytics reuse.
- `storage/ibkr_marketstore.py`: Redis TS streams for market data (underlying L1, option L1, tick-by-tick) keyed by symbol/expiry/strike with short retention (intraday + 3 days) and aggregation downsampling.
- `storage/ibkr_depth_store.py`: Order book snapshots stored in Redis Streams/JSON with depth versioning for analytics replay.
- `storage/ibkr_events.py`: persists orders, fills, account updates, error events, and pace warnings using Redis Hash + TimeSeries; archives daily CSV/Parquet extracts for compliance.
- Prometheus metrics: `ibkr_market_data_events_total`, `ibkr_order_latency_ms`, `ibkr_disconnects_total`, `ibkr_error_events_total`.
- Grafana dashboard for connectivity, order lifecycle (submit → fill), fill rates, and paper P&L preview.

### Implementation Notes
- Connect to the existing TWS instance (paper/live) configured on `127.0.0.1:7497`; fallback to Dockerized gateway only if the local instance is unavailable. Manage unique `clientId`s per module to avoid collisions.
- Use `ib_insync` for the API surface; bridge to asyncio via `IB.run`/`asyncio.get_event_loop()` and expose async-friendly wrappers so ingestion and execution remain non-blocking.
- ClientId allocation (reserve values to avoid clashes with TWS UI): ingestion `101`, execution `201`, analytics `301`, reporting/simulation `401`.
- Data coverage expectations (with live entitlements):
  - **Underlying Level I** – `reqMktData` for target underlyings (bid/ask, last, volume, VWAP, realtime volume, tick-by-tick trade/bid-ask feed via `reqTickByTickData`).
  - **Options Level I** – `reqSecDefOptParams` to enumerate strikes/expiries, then `reqMktData` for the 0DTE/1DTE/14-45 DTE strikes configured; include `genericTickList='106,104,233'` for Greeks, option volume, and implied volatility.
  - **Account & Portfolio** – `reqAccountUpdates`, `reqPnL`, `reqPnLSingle` to capture account health, realized/unrealized P&L, margin, and buying power.
  - **Level II Depth** – `reqMktDepth` per symbol using explicit exchange codes (no SMART). Configure `depth_exchanges` (e.g., `SPY@ARCA`, `QQQ@ISLAND`, option contracts `CBOE`, `BOX`, etc.) to match subscribed Level II feeds. Aggregate snapshots into standardized order book structures for analytics.
- Level II requires subscription entitlements; guard module execution so depth requests are issued only for configured exchange codes. Validate exchange/venue mappings at startup and surface errors in logs + Prometheus (`ibkr_depth_errors_total`).
- TWS allows only three simultaneous `reqMktDepth` subscriptions; implement a rotating scheduler that cycles through the configured depth symbols (e.g., `SPY`, `QQQ`, `IWM`, `SPX`, key single names) with configurable dwell time. Persist the last depth snapshot so analytics retain the most recent view while symbols rotate.
- Set `marketDataType` according to environment (1=live, 3=delayed-frozen for tests) and downgrade gracefully if entitlements are missing.
- Respect IBKR pacing: throttle `reqMktData`, `reqMktDepth`, and order submissions using a Redis-backed limiter (e.g., 50 market data/sec, 5 order placements/sec). Surface pacing waits as Prometheus metrics.
- Provide simulation mode using recorded sessions for offline development and automated tests when TWS is unavailable.
- Ensure risk checks include buying power, per-symbol delta limits, outstanding order exposure, and regulatory restrictions (pattern day trading, OCC limits).
- Storage strategy after ingestion:
  - **Market data**: Redis TS keys (`ibkr:underlying:{symbol}`, `ibkr:option:{symbol}:{expiry}:{strike}:{right}`) with 48h full-resolution retention and downsampling to 1m/5m cadences for analytics; tick-by-tick feeds persisted to Redis Streams for replay.
  - **Aggregated bars**: Redis TS (`ibkr:bars:{symbol}:{interval}`) containing 5s source data rolled to 1m/2m/5m OHLCV bars for analytics/MOC predictor.
  - **Depth ladders**: Redis JSON/Hash entries storing best 10 levels per venue with timestamps; maintain TTL refresh when new snapshots arrive so data stays valid between rotation windows. Archive minute snapshots for liquidity analytics.
  - **Orders & fills**: Redis Hash per order ID (`orders:{ib_order_id}`) with statuses, timestamps, and metadata; TimeSeries tracking submission→fill latency. Nightly Parquet exports (`archive/ibkr/orders/{date}.parquet`) for audit.
  - **Account state**: Redis Hash for balances/margin, TimeSeries for PnL (`account:pnl`) sampled via `reqPnL`/`reqPnLSingle` feeds.

### Testing
- Unit tests mocking the `ib_insync` client and verifying contract builder correctness.
- Live integration suite `pytest -m live_ibkr` (paper account):
  - Gated by `LIVE_IBKR_TESTS=1`, requires TWS running on port 7497 with configured credentials.
  - Subscribes to a limited option chain, validates market data streaming into Redis, confirms Level I + Level II depth snapshots are ingested, and places/cancels micro orders to confirm order state transitions without fills.
  - Emits Prometheus counters (`test_live_ibkr_success_total`, `test_live_ibkr_depth_success_total`, `test_live_ibkr_pacing_wait_seconds`).
- Replay harness using recorded `.ibkr` market data, depth ladders, and execution logs to validate analytics module inputs when TWS is offline.

### Exit Criteria
- Stable connection for 72h with automated recovery and no missed heartbeats (Grafana alert silence maintained).
- Paper account orders (test contracts) processed end-to-end with telemetry recorded and Redis state in sync with IBKR account snapshot.
- Runbook (`docs/module2_ibkr.md`) covering local TWS expectations, clientId management, pacing limits, failure recovery, and simulation mode usage.

---

## 4. Module 3 – Analytics Core
**Dependencies**: Modules 0-2

### Scope
Compute all analytics required for strategy sophistication while relying on simplified, modular components. Operate on Redis TimeSeries data and publish results for downstream consumption.

### Deliverables
- `analytics/greeks_engine.py`: vectorized Greeks (Delta, Gamma, Vega, Theta, Rho, Vanna, Vomma, Charm) using Black-Scholes-Merton with implied vol from AlphaVantage/IBKR; references Hull & Jäckel for validation. Pulls option quotes from Redis stores (`options:{symbol}`, `ibkr:option:*`), publishes to Redis TS (`analytics:greeks:{symbol}`) with 5s validity (faster for 0DTE).
- `analytics/regime_classifier.py`: multi-factor regime detection combining realized vol (5s/1m/5m bars), breadth (adv/dec lines), macro overlays, implied vol spreads; documents methodology (Lo, Markov switching). Stores state in Redis Hash + TS (`analytics:regime`) with 60s validity and change logs.
- `analytics/liquidity_monitor.py`: computes bid/ask spreads, market depth decay, order-book imbalance, slippage estimates. Consumes L1/L2 feeds (`ibkr:underlying:*`, `ibkr:depth:*`) and stores liquidity scores in Redis TS (`analytics:liquidity:{symbol}`) refreshed every 5s.
- `analytics/vpin.py`: Volume-Synchronized Probability of Informed Trading using tick-by-tick trades and 5s aggregated volume buckets; references Easley et al. methodology. Writes toxicity metrics to Redis TS (`analytics:vpin:{symbol}`) with 10s cadence.
- `analytics/macro_overlay.py`: integrates AlphaVantage macro feeds (CPI, GDP, yields, sentiment for equities) and cross-asset correlations to produce macro regime scores and event alerts. Outputs to Redis Hash (`analytics:macro:{symbol}`) with hourly/daily cadence per series.
- `analytics/risk_attribution.py`: factor/PCA decomposition for portfolio exposures using recent returns windows (5m/60m). References RiskMetrics, Qian. Stores factor exposures in Redis TS (`analytics:risk:{symbol}`) and archives daily Parquet snapshots.
- `analytics/cross_asset_stress.py`: scenario engine combining macro overlays, commodity/rates shocks, FX; estimates portfolio P&L under stress. Stores stress indices and scenario results in Redis Hash (`analytics:stress:{scenario}`) updated every 15m.
- `analytics/moc_predictor.py`: Market-on-Close imbalance predictor for `SPY`, `QQQ`, `IWM`, `SPX` using IBKR tick data, 5s→1m/2m/5m bar aggregates, L2 depth, historical imbalance archives. Outputs projected imbalance + confidence to Redis TS (`analytics:moc:{symbol}`) with 30s cadence; includes historical backtest logs.
- Event bus (Redis Pub/Sub or queue) broadcasting analytics updates with timestamps and provenance metadata.
- Prometheus metrics: `analytics_compute_latency_ms{module=…}`, `analytics_failure_total`, `analytics_stale_results_total`, `analytics_input_lag_seconds`.
- Grafana **Analytics Health** dashboard showing freshness, latency distributions, VPIN trend, liquidity heatmap, and MOC prediction accuracy.

### Implementation Notes
- Data dependencies:
  - Greeks: Redis TS from Module 1 (`options:{symbol}`) + Module 2 (`ibkr:option:*`), vol surfaces from archives.
  - Liquidity/VPIN/MOC: Module 2 tick feeds (`ibkr:tick`, `ibkr:depth`), aggregated bars produced in analytics job.
  - Macro overlay/cross-asset stress: Module 1 macro/micro AlphaVantage series.
  - Risk attribution: Module 5 positions + historical prices from archives.
- Recompute cadence & validity:
  - 0DTE/1DTE analytics (Greeks, liquidity, VPIN, MOC) refresh every tick with 5s validity windows; ensure `valid_until` metadata and rapid expiry to avoid stale consumption.
  - Swing analytics (macro overlay, risk attribution, stress) refresh on 5m/15m/hourly intervals with longer validity.
- Scheduler strategy: Use event-driven priority queues; for fast instruments recompute on each tick but coalesce updates within 250 ms windows to avoid thrash. Document logic clearly for maintainability.
- Mathematical references recorded in `docs/module3_formulas.md` with links to source literature (Hull, Jäckel, Easley, Lo, Qian).
- Persist outputs to Redis TS/Hash with TTL matching validity windows; include `source`, `computed_at`, `valid_until` fields for downstream checks.
- Aggregated bars: produce 5s bars from tick data, roll up to 1m/2m/5m stored in Redis TS (`ibkr:bars:{symbol}:{interval}`) for analytics reuse.

### Testing
- Unit tests with synthetic fixtures validating formulas against known references (Hull Greeks tables, sample VPIN datasets).
- Replay tests using recorded AlphaVantage/IBKR data to verify timing and accuracy; compare computed Greeks vs IBKR-provided values, MOC predictions vs historical official imbalance.
- Statistical validation for regime classifier (confusion matrices vs historical regimes) and VPIN (correlation with volatility spikes).
- Metrics-based alerts when analytics lag >1s for 0DTE or >5s for swing analytics; dashboards monitored during tests.

### Exit Criteria
- 0DTE/1DTE analytics latency <1s; swing analytics latency <5s across watchlist.
- Documentation of formulas, dependencies, tuning knobs, and MOC predictor methodology (`docs/module3_analytics.md`, `docs/module3_formulas.md`).
- Validation suite comparing analytics outputs against reference calculations passes; Grafana dashboard shows green metrics for freshness/accuracy.

---

## 5. Module 4 – Signal Engine & Research
**Dependencies**: Modules 0-3

### Scope
Generate trade signals for 0DTE, 1DTE, and swing buckets using analytics outputs, validate via risk/compliance rules, and maintain a unified research/testing environment with modern tooling.

### Deliverables
- `signals/signal_generator.py`: orchestrates bucket-specific strategies with modular pipelines, idempotent signal IDs, and metadata linking to analytics inputs.
- `signals/strategies/zero_dte.py`: 0DTE strategy module focusing on gamma scalping and liquidity-responsive entries for `SPY`, `QQQ`, `IWM`, `SPX`; leverages Greeks, liquidity, VPIN, MOC predictor.
- `signals/strategies/one_dte.py`: 1DTE overnight strategy incorporating regime classifier, macro overlay, and early imbalance clues for same symbols.
- `signals/strategies/swing.py`: 14-45 DTE strategy using macro overlay, risk attribution, cross-asset stress for broader watchlist (Magnificent Seven + extended names).
- `signals/strategies/moc_imbalance.py`: MOC imbalance trade logic using projected imbalance from analytics, liquidity constraints, and historical patterns.
- `signals/validator.py`: validates liquidity (min depth, max spread), exposure (per-symbol delta/gamma caps), compliance (trading hours, restricted assets) before publishing to execution bus.
- `signals/publisher.py`: publishes accepted signals to execution module with correlation IDs, required execution parameters, and callback hooks for fill notifications.
- Research toolkit: vectorized backtesting using **vectorbt** and **backtrader**, scenario analysis scripts, data loaders for archived AlphaVantage/IBKR datasets.
- Backtest orchestration scripts (`research/run_backtest.py`) with config templates for each strategy bucket.
- Prometheus metrics: `signals_generated_total`, `signals_rejected_total{reason=…}`, `signal_latency_ms`, `signals_per_bucket_total`.
- Grafana **Signals & Research** dashboard showing signal volume by bucket, validation rejects, backtest outcomes, and execution latency hand-off.

### Implementation Notes
- Strategy orchestration:
  - Event-driven: subscribe to analytics updates (Greeks, liquidity, regime, MOC predictor) and schedule strategy evaluation per bucket.
  - 0DTE pipeline: evaluate gamma exposure, VPIN thresholds, liquidity score, and MOC signal readiness; ensure signals include target strikes, desired delta, expiration time, exit criteria.
  - 1DTE pipeline: incorporate macro overlay changes, overnight risk filters, and closing imbalance forecasting.
  - Swing pipeline: evaluate macro regime, earnings calendars, risk attribution deltas, cross-asset stress; generate swing entries with defined time horizons.
  - MOC pipeline: run separately within last 60 minutes, using projected imbalance, liquidity, and historical fill metrics.
- Validation layer: check liquidity (depth >= threshold, spread <= max), exposure (delta/gamma within limits, portfolio concentration), compliance (trading window, restricted symbols, regulatory flags). Use data from Module 5 risk configs and Module 2 liquidity store.
- Signals carry metadata: analytics snapshot ID, assumption set, recommended order type, confidence score, and social publishing flags (premium/basic/free eligibility, redaction levels).
- Publisher requires ACK from execution module (Module 5) before marking signal active; stores pending state in Redis and awaits fill events to trigger downstream social workflows (Module 7).
- Remove `signals/performance_tracker.py` responsibility—realized P&L tracking moves to Module 5 Execution & Risk.
- Research environment: maintain parity between live strategy code and backtest implementations; config-driven parameter sets stored in `config/signals/*.yaml`.
- Backtests produce artifacts (Parquet, charts) for reporting; integrate with Module 6 reporting pipeline.

### Testing
- Deterministic replay tests for each strategy bucket using recorded data (0DTE/1DTE/MOC) to ensure signals reproduce expected trades.
- Validation tests injecting scenarios (low liquidity, exposure breaches) to confirm `signals/validator.py` blocks and logs appropriately.
- Cross-framework backtests comparing vectorbt/backtrader outputs for sample strategies; ensure parity within tolerance.
- Load tests generating burst analytics events to verify signal latency stays <100 ms.

### Exit Criteria
- Signals delivered with <100 ms added latency beyond analytics for all buckets.
- Strategy-specific backtests cover last 12 months and align within 5% of live or paper metrics.
- Documentation (`docs/module4_signals.md`) includes strategy rules, analytics dependencies, validation criteria, and research workflow (vectorbt/backtrader parity).

---

## 6. Module 5 – Execution & Real-Time Risk
**Dependencies**: Modules 0-4

### Scope
Translate validated signals into IBKR orders, manage portfolio exposures, enforce risk limits, and provide automated de-risking actions.

### Deliverables
- `execution/order_router.py`: chooses order types (limit, marketable limit, adaptive), handles staged orders, order throttling, and acknowledgements back to signal publisher.
- `execution/sizing.py`: position sizing engine incorporating delta targets, volatility, and account constraints; supports scaling by confidence/portfolio risk.
- `execution/trailing_stop_manager.py`: dynamic stop and take-profit module supporting trailing stops (percent/ATR/delta-based), profit lock tightening for large gains (e.g., 300% MOC spikes).
- `risk/real_time_limits.py`: monitors delta/gamma/theta caps, drawdown limits, open order counts, and signals forced exits when breached.
- `execution/fill_dispatcher.py`: listens for fills from IBKR, enriches with signal metadata, and forwards to publisher/social pipeline (premium/basic/free timing rules).
- `risk/alerting.py`: pushes urgent notifications via Discord/Telegram webhooks (Module 7 integration) for risk events and trailing-stop triggers.
- Fail-safe toggles (Redis flags) to halt trading, flatten positions, or downgrade to observation mode.
- Prometheus metrics: `orders_submitted_total`, `order_failures_total`, `risk_limit_breaches_total`, `execution_latency_ms`, `trailing_stop_adjustments_total`, `fill_dispatch_events_total`.
- Grafana **Execution & Risk** dashboard with latency waterfall, exposure gauges, trailing-stop activity, and alert history.

### Implementation Notes
- Maintain correlation IDs across signal → order → fill for auditability and to synchronize with `signals/publisher.py`.
- Use async queues to decouple signal ingestion from IBKR order submission; support re-ordering and retries with exponential backoff.
- Trailing stops: configurable templates per strategy (percent, ATR, delta-based) with dynamic tightening when unrealized P&L crosses thresholds (e.g., +100%, +200%, +300%). Ensure stops never reverse into loss once locked.
- Execution acknowledges each signal back to publisher after order acceptance, and pushes fill/exit events to Module 7 social channels: premium immediately, basic after 60s with redactions, free after 5 minutes with additional masking.
- Implement circuit breakers on repeated order rejection patterns; trigger risk alerts and optionally pause strategy bucket.
- Size adjustments consider current portfolio gamma/theta exposure and available buying power; integrate with risk limits to prevent oversizing.

### Testing
- Paper account end-to-end tests confirming signal triggers order submission, trailing stops adjustments, and fill acknowledgements back to publisher.
- Stress tests injecting burst signals to measure queue depth (<1s) and ensure trailing-stop manager scales without lag.
- Simulation tests verifying risk module triggers halts when thresholds breached and social dispatch timing (premium, basic, free) fires correctly with redactions.

### Exit Criteria
- Automated execution stable over full trading session without manual intervention.
- Trailing-stop logic validated in live/paper runs (no profitable trade reverses past locked level).
- Fill dispatch pipeline delivers premium/basic/free notifications with correct timing and redactions.
- Risk alerts proven in simulation and visible in dashboards/notifications.
- Runbook (`docs/module5_execution_risk.md`) outlining ops procedures, trailing-stop configuration, social dispatch dependencies, and emergency playbooks.

---

## 7. Module 6 – Reporting & AI Oversight
**Dependencies**: Modules 0-5

### Scope
Generate premium-grade reports and AI-driven oversight to maintain transparency, compliance, and competitive analytics edge.

- `reporting/report_generator.py`: builds state-of-the-art hedge-fund-grade reports (pre-market, intraday, market-close) with Plotly/LaTeX visuals, options analytics, strategy commentary, risk disclosure, and trailing-stop summaries; automatically forwards tiered versions to Module 7 social channels.
- `reporting/chart_builder.py`: reusable chart templates (aggregated Greeks, liquidity heatmaps, MOC accuracy, P&L attribution) aligned with Grafana panels.
- `reporting/templates/`: Jinja2/LaTeX templates for premium (full), basic (reduced detail), and free (headline) variants with layered redactions to protect proprietary signals.
- `reporting/scheduler.py`: orchestrates report generation per cadence (EOD + intraday alerts) and pushes artifacts to storage and Module 7.
- `reporting/narrative_writer.py`: leverages Claude/OpenAI with prompt guardrails and human-in-loop approvals; crafts professional hedge-fund style commentary per section while omitting confidential parameters.
- `ai_overseer/anomaly_detector.py`: monitors analytics/execution streams for anomalies (slippage spikes, latency, signal drift) and records findings.
- `ai_overseer/trade_validator.py`: reviews pending signals/orders for compliance, risk deviations, and trailing-stop adherence; feeds results to Module 5 risk alerts.
- `ai_overseer/explainability.py`: generates audit summaries linking analytics inputs to trade decisions for regulators/clients.
- Report/archive storage: Versioned artifacts in `reports/{date}/` (PDF/HTML/JSON), metadata in Redis, optional upload to S3/GCS when Module 8 ready; includes audit trail of redaction decisions and reviewer approvals.
- Prometheus metrics: `reports_generated_total`, `report_duration_ms`, `ai_alerts_total{severity=…}`, `narrative_review_pending`.
- Grafana **Reporting & AI** dashboard tracking generation SLA, AI anomaly counts, approval queues, and distribution status.

### Implementation Notes
- Data sources: combine Module 3 analytics (Greeks, VPIN, liquidity, macro overlays, MOC predictor accuracy), Module 5 execution/fill logs and trailing-stop adjustments, Module 4 signal metadata, Module 7 subscriber insights, and AlphaVantage macro/news data for narrative context.
- Report cadences & tiering:
  - **Premium** – Pre-market (full market setup, overnight review, macro calendar, signal outlook); Intraday (mid-session performance, live trades, risk posture); Market Close (comprehensive recap, P&L, strategy notes). Delivered immediately to premium Discord/email.
  - **Basic** – Pre-market only with key themes, limited analytics breakdown, sanitized trade outlook.
  - **Free** – Single daily highlight summary (top market movers, broad insights) without proprietary metrics.
- Premium report structure (examples):
  1. Executive Summary & Market Regime (regime classifier, macro overlay)
  2. Options & Liquidity Dashboard (Greeks aggregates, VPIN trends, depth heatmaps)
  3. Strategy Activity (0DTE, 1DTE, swing, MOC trades with rationale, but abstracted thresholds)
  4. Risk & Exposure (delta/gamma/theta, stress scenarios, trailing-stop adjustments)
  5. Upcoming Catalysts (earnings, macro events)
  6. AI Oversight Notes (anomaly detections, validator results, explainability summaries)
- Redaction policy: templates define sections/fields removed or generalized for Basic/Free tiers (e.g., strip strike levels, position sizing, proprietary thresholds) while retaining professional tone.
- Storage & retention: Keep 30 days of reports locally, archive older artifacts to cloud storage; maintain manifest for audit and regenerate capability.
- AI oversight: anomaly detector subscribes to analytics/execution buses, raising alerts to Module 5 risk and Module 7 social. Trade validator runs pre-trade (signals) and post-trade (fills) checks; results appended to reports. Explainability module links analytics inputs to decisions without revealing parameter weights.
- Human review workflow: allow manual approval/edits before public distribution; log reviewer identity, version diffs, and sign-off timestamps.
- Social integration: scheduler hands artifacts + summary blurbs to Module 7 for premium/basic/free dispatch aligned with timing rules (immediate/60s/5m). Ensure retries/backoff for failed posts and maintain compliance logs.
- Security & compliance: sanitize narratives and visuals to avoid disclosing secret sauce (e.g., show normalized scores instead of raw thresholds); embed tier-specific disclaimers.
- Observability: emit metrics for generation duration, AI inference latency, approval backlog, distribution success/failure, and redaction coverage.

### Testing
- Snapshot/regression tests for report rendering across premium/basic/free templates (visual diff + PDF checksum).
- Unit tests for chart builder to validate data slicing and formatting.
- AI prompt evaluation tests (golden responses, toxicity/compliance filters) with fallback coverage when AI unavailable.
- Integration tests ensuring scheduler triggers Social Module 7 with correct redaction timing and retries; verify premium/basic/free artifacts delivered.
- Load tests simulating multiple trading days to ensure report generation meets SLA (<2 minutes for EOD premium).

### Exit Criteria
- Automated report generation and AI oversight run on schedule with operator notifications and zero missed cadences.
- AI anomaly/validator outputs integrated into Module 5 risk alerts and Module 7 notifications.
- Documentation (`docs/module6_reporting_ai.md`) detailing templates, approval flow, AI safeguards, redaction rules per tier, and incident escalation.

---

## 8. Module 7 – Social Distribution & Premium Delivery
**Dependencies**: Modules 0-6

### Scope
Distribute analytics, signals, and premium content to subscribers across Discord, Telegram, Twitter, email, and other channels while enforcing entitlements.

### Deliverables
- `social/discord_bot.py`: posts alerts, reports, fill notifications, and status updates to gated channels; supports command interface for summaries and handles staged disclosures (premium immediate, basic +60s, free +5m).
- `social/telegram_bot.py`: broadcasts accepted signals (premium/basic pacing), provides interactive approval commands for operator (e.g., /approve, /halt) usable via mobile, and relays risk alerts.
- `social/twitter_publisher.py`: schedules public teasers (“400% move today, join premium”) with compliance filters and throttling.
- `social/reddit_publisher.py`: posts curated highlights to Reddit (personal profile + cross-post to WallStreetBets) with safe messaging templates and rate limiting.
- `social/email_dispatcher.py`: sends newsletters (daily/weekly) using templated content aligned with Module 6 reports.
- Webhook integration from Module 5 risk alerts and fill dispatcher (with staged redactions) and from Module 6 reports.
- Prometheus metrics: `social_messages_sent_total{channel=…}`, `social_failures_total`, `subscriber_active_total`.
- Grafana **Distribution & Revenue** dashboard tracking message success, subscriber churn, and conversion metrics.

- Use async clients (`aiohttp`, `python-telegram-bot`, `discord.py`) with retries and backoff.
- Content templating with Jinja2 to maintain consistency across channels and tiered redactions.
- Telegram bot exposes command set for approvals (`/approve_signal`, `/halt_strategy`, `/status`) with permission checks; logs decisions to Redis/Audit trail.
- Discord integration leverages WHOP for role/channel management; module focuses on message content and timing.
- Twitter/Reddit posts adhere to safe messaging templates (no confidential parameters) and rate limits; integrate with compliance review where needed.
- Email dispatcher reuses Module 6 templates, generating tiered newsletters; sends via transactional email service (SendGrid/Mailgun) with failover.
- Audit log for every outbound message stored in Redis/Parquet for compliance and replay; include message id, channel, payload hash, success/failure.
- Observability: metrics for message success/failure, approval actions, queue latency.

- Sandbox/test channels for each platform; integration tests send sample payloads and confirm reception (premium/basic/free timing).
- Unit tests for templating and redaction logic to ensure confidential data not leaked across tiers.
- Telegram approval flow tests using mocked bot interactions; ensure commands update Redis state and trigger correct responses.
- Observability tests verifying metrics increment, alerts fire on failure, and retry logic functions.

- End-to-end flow from signal/report to subscriber channels works reliably with logs and metrics across Discord/Telegram/Twitter/email.
- Documentation (`docs/module7_social.md`) capturing onboarding steps, approval command reference, content cadence, and redaction policies.

---

## 9. Module 8 – Deployment & GCP Readiness
**Dependencies**: Modules 0-7

### Scope
Prepare infrastructure-as-code and operational playbooks to deploy the platform to Google Cloud while preserving Redis TimeSeries capabilities and observability stack.

### Deliverables
- Terraform modules (minimal) covering: VPC + subnets, GKE cluster, Artifact Registry, Secret Manager, Cloud Storage bucket for archives, IAM bindings. Configure remote state in GCS (e.g., `gs://quanticity-terraform-state` with keys `env/<environment>/terraform.tfstate`).
- Kubernetes manifests/Kustomize for application deployments, Redis Stack (StatefulSet with persistence), Prometheus/Grafana via Helm/Operator.
- CI/CD pipeline (GitHub Actions or Cloud Build) building Docker images, pushing to Artifact Registry, deploying to GKE with kubectl/Helm.
- Secrets management: Secret Manager integration with workload identity; local `.env` → Secret Manager sync script.
- Redis Stack strategy: validate Memorystore for Redis vs self-managed Redis Stack (to keep TimeSeries); document steps for either path.
- Observability bridging: managed Prometheus or self-hosted with exporters; ensure Grafana dashboards loaded via ConfigMaps.
- Disaster recovery checklist: Redis snapshots to Cloud Storage, application backup/redeploy steps.

### Implementation Notes
- Parameterize environment config for dev/staging/prod; reuse Module 0 config patterns.
- Whitelist outbound network access (AlphaVantage, IBKR, messaging APIs) via firewall rules/NAT.
- Keep cost/scaling plan simple: start with single replica per service; document when to scale ingestion/analytics.

### Testing
- Infrastructure validation: Terraform plan/apply (staging), `kubectl get` smoke tests.
- Application smoke tests in GKE using existing end-to-end suite; compare metrics to local baseline.
- Redis failover simulation (pod delete) ensuring persistence/restore works.
- CI gate: require `make lint`, `make test`, and module-specific live suites (`pytest -m live_alpha`, `pytest -m live_ibkr`) when credentials are available before pushing images to Artifact Registry.

### Exit Criteria
- Reproducible staging environment in GCP with metrics/dashboards intact and CI/CD pipeline green.
- Deployment runbook (`docs/module8_deployment_gcp.md`) finalized with minimal set of steps.

---

## 10. Testing & Quality Automation Framework
**Cross-cutting module across all stages**

### Strategy
- **Unit tests**: pytest with fixtures; fast feedback.
- **Integration tests**: `pytest -m live_alpha` and `pytest -m live_ibkr` hitting real services under strict budgets, with metrics piped to Prometheus via pushgateway or direct instrumentation.
- **End-to-end smoke**: Compose stack scenario verifying ingestion → analytics → signal → execution pipeline; run nightly.
- **Regression/backfill tests**: use archived data to ensure analytics and signals remain stable across releases.

### Tooling
- Pytest with coverage.py; optional Hypothesis for property testing on analytics modules.
- Pre-commit hooks (black, ruff, mypy, bandit, pip-audit) to keep code quality consistent.
- Simple tox/nox configs to run unit/integration suites locally.
- Test observability: Grafana dashboard showing pass/fail counts, latency, API call consumption.

### Policies
- Live tests require explicit env flags; CI triggers manual workflows off-peak to avoid unintended calls.
- If tests hit rate-limit errors, raise Prometheus alerts and adjust schedules/quotas.
- Each module contributes relevant tests (e.g., Module 5 execution stress) before exit sign-off.

---

## 11. Performance Playbook
- **Concurrency**: use asyncio + `asyncio.Semaphore` to bound concurrency; prefer `httpx` with HTTP/2 for AlphaVantage to reduce handshake overhead.
- **Batching**: group Redis writes with `TS.MADD`, leverage pipeline contexts for hash updates.
- **Vectorization**: rely on numpy/pandas/numba for analytics; avoid Python loops in critical paths.
- **Profiling**: integrate `py-spy`/`pyinstrument` profiling commands (`make profile-ingestion`, `make profile-analytics`).
- **Latency Budgets**:
  - Ingestion request <50 ms
  - Redis write <5 ms
  - Analytics update <100 ms
  - Signal evaluation <100 ms
  - Execution dispatch <100 ms (paper/live)
- **Monitoring**: Prometheus histograms for each budget with Grafana alerts when p95 exceeds thresholds.
- **Hardware Utilization**: enable uvloop on Linux; configure process pools for CPU-bound analytics; use shared memory for heavy data.

---

## 12. Sequential Roadmap & Governance
1. **Module 0 – Environment & Observability** (Week 1) – deliver Compose stack, baseline dashboards, smoke tests.
2. **Module 1 – AlphaVantage REST & Storage** (Weeks 2-3) – ingestion, rate limiting, Redis persistence, live tests.
3. **Module 2 – IBKR Integration** (Weeks 4-5) – market data + order path, paper trading validation.
4. **Module 3 – Analytics Core** (Weeks 6-7) – analytics pipelines, performance tuning, dashboards.
5. **Module 4 – Signals & Research** (Weeks 8-9) – strategy logic, validator, modern backtesting.
6. **Module 5 – Execution & Risk** (Weeks 10-11) – order routing, risk automation.
7. **Module 6 – Reporting & AI** (Week 12) – automated reports, AI oversight.
8. **Module 7 – Social Distribution** (Week 13) – premium channel delivery and entitlement controls.
9. **Module 8 – Deployment & GCP** (Weeks 14-15) – Terraform, GKE, Redis Stack in cloud.

### Module Exit Checklist
- Code merged with review sign-off.
- Config templates updated.
- Docker Compose updated and verified.
- Unit + integration tests (including live where required) green; dashboards monitored during runs.
- Documentation/runbooks completed.
- Performance metrics within budget.
- Security and compliance review complete.

---

## 13. Documentation & Knowledge Base
- Maintain `docs/` module runbooks (`module0_environment.md` ... `module8_deployment_gcp.md`) alongside this architecture blueprint.
- Capture quantitative definitions in `docs/module3_formulas.md` and update the file whenever analytics logic changes.
- Mirror architecture decisions into the relevant module runbook and note outstanding follow-ups directly within each document.
- Keep a running change log of module completion checkpoints and decision records with the associated runbook.

---

## 14. Assessment Summary
Reorganizing the system into sequential, end-to-end modules backed by Docker Compose, Prometheus, and Grafana preserves the project’s sophistication while making execution manageable for a single developer. The blueprint enforces:
- Clear build boundaries with acceptance criteria before advancing.
- Direct REST integrations and high-performance analytics without unnecessary infrastructure sprawl.
- Embedded observability, testing, and social distribution to support premium offerings.
- Straightforward migration path to GCP with Redis TimeSeries continuity.

Following this plan keeps complexity aligned with value—every module delivers a complete, production-quality capability before the next begins.