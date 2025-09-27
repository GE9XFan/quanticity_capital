# Quantum Trading System - Complete Project Architecture

## 🎯 System Overview
**Options-Only Trading System** focusing on:
- **0DTE** (Same-day expiry) - High gamma scalping
- **1DTE** (Next-day expiry) - Overnight events
- **14+ DTE** (2-6 weeks) - Trend following
- **Long positions only** - Buying calls and puts (no naked selling)
- **Configurable symbols** - User-defined watchlist

## 🏗️ Project Structure
```
quantum-trading-system/
│
├── config/
│   ├── credentials.yaml          # API keys, Redis config
│   ├── trading_params.yaml       # Strategy parameters
│   ├── ai_config.yaml           # AI model configurations
│   └── social_config.yaml       # Discord, Telegram settings
│
├── data_ingestion/
│   ├── alphavantage_client.py   # AlphaVantage wrapper
│   ├── ibkr_client.py          # ib_async integration
│   ├── data_normalizer.py      # Standardize data formats
│   └── stream_manager.py       # Real-time data orchestration
│
├── storage/
│   ├── redis_timeseries.py     # Redis TS operations
│   ├── cache_manager.py        # L1/L2 caching for speed
│   └── data_persistence.py     # Backup to disk
│
├── analytics/
│   ├── greeks_engine.py        # Options Greeks calculations
│   ├── regime_classifier.py    # Volatility regime detection
│   ├── liquidity_monitor.py    # Order book health metrics
│   ├── vpin_calculator.py      # Order flow toxicity
│   ├── macro_overlay.py        # Economic indicators
│   ├── microstructure.py       # Market microstructure analytics
│   └── risk_attribution.py     # PCA-based risk decomposition
│
├── signals/
│   ├── signal_generator.py     # Trading signal logic
│   ├── backtest_engine.py      # Zipline integration
│   ├── signal_validator.py     # Pre-trade validation
│   └── performance_tracker.py  # Real-time P&L
│
├── execution/
│   ├── order_manager.py        # IBKR order execution
│   ├── position_manager.py     # Position tracking
│   ├── risk_manager.py         # Risk limits & controls
│   └── portfolio_optimizer.py  # Position sizing
│
├── ai_overseer/
│   ├── market_analyst.py       # AI market commentary
│   ├── trade_validator.py      # AI trade verification
│   ├── anomaly_detector.py     # Pattern recognition
│   ├── risk_alerter.py        # Intelligent alerts
│   └── claude_integration.py   # Claude API wrapper
│
├── reporting/
│   ├── report_generator.py     # PDF creation engine
│   ├── chart_builder.py        # Plotly/Matplotlib visuals
│   ├── market_narrator.py     # AI-powered descriptions
│   └── templates/              # Report templates
│
├── social/
│   ├── discord_bot.py          # Discord integration
│   ├── telegram_bot.py         # Telegram integration
│   ├── broadcast_manager.py    # Multi-channel publishing
│   └── subscriber_manager.py   # Premium user management
│
├── tests/
├── logs/
├── docker-compose.yml
├── requirements.txt
└── main.py                      # System orchestrator
```

---

## 📊 Layer 1: Data Ingestion

### AlphaVantage Premium Integration
**Repository**: https://github.com/RomelTorres/alpha_vantage
**Python Package**: `alpha_vantage` (v2.3.1)

#### Ingestion Responsibilities
- Wrap the official `alpha_vantage.options.Options` client inside `data_ingestion/alphavantage_client.py`.
- Expose helpers for the core market-data calls: `Options.get_realtime_options` (full chain or specific contract, always with `requiredGreeks=True`), `Options.get_historical_options` (daily snapshot back to 2008-01-01), and `TimeSeries.get_intraday` for the underlying spot feed used in hedging and sanity checks.
- Leverage `alpha_vantage.techindicators.TechIndicators` to stream Bollinger Bands (`get_bbands`), VWAP (`get_vwap`), and MACD (`get_macd`) for the configured symbols; cache these curve outputs per symbol so analytics can enrich signals without re-polling the API.
- Normalize the AlphaVantage payload into internal DTOs—`OptionQuote` for options and `IndicatorSeries` for technicals—so downstream layers stay transport agnostic.

#### Rate Limit & Concurrency Strategy
- Premium entitlement affords 600 calls per minute; dedicate a `RateLimitController` (Redis token bucket) that tracks calls per endpoint to support concurrent symbol polling without tripping hard limits.
- Batch polling by grouping contracts per symbol: one chain request returns all strikes for a tenor, so budget ~10 requests per symbol per refresh cycle (0DTE, 1DTE, 14-45 DTE buckets).
- The upstream library is synchronous; dispatch calls through an `asyncio` executor pool (`run_in_executor`) so the ingestion service can overlap I/O while keeping a single code path. Retry jitter (50-150 ms) smooths bursts.

#### Resilience & Monitoring
- Map AlphaVantage error payloads to typed exceptions (`LimitExceeded`, `ServiceUnavailable`, `ContractNotFound`) and surface them to the observability layer for dashboard alerts.
- Cache the most recent successful chain in Redis with a millisecond timestamp; if a refresh fails, fall back to cached data (flagged `stale=true`) so analytics never receives an empty dataset.
- Persist raw responses to nightly Parquet snapshots for replay/debugging and to support regression tests against historical anomalies.

#### Technical Indicator Support
- Indicators share the same call quota; stagger their refresh cadence (e.g., 1-minute rolling window) and reuse cached intraday prices for validation.
- Store indicator series in Redis TS under `tech:{symbol}:{indicator}` with explicit retention rules (e.g., 3 days hot + parquet archive) to feed the analytics factor library.
- When an indicator call fails, fall back to locally computed values derived from the cached underlying prices to keep the signal pipeline consistent.

#### Macro & Sentiment Extensions
- Tap `AlphaIntelligence` for `get_news_sentiment` (AI overseer narratives) and `get_top_gainers/losers/most_active` to auto-refresh the configurable watchlist and spotlight unusual flows.
- Use `EconIndicators` to hydrate the macro overlay with GDP, CPI, FFR, unemployment, and yield-curve series; schedule polls hourly/daily and archive to Parquet so factor models can run offline.
- Ingest `Commodities` (WTI, Brent, NatGas, copper, grains) to feed the cross-asset stress index with macro shock signals.
- Pull fundamentals via `FundamentalData` (overview, earnings surprises, dividends, balance sheet) to power AI risk narratives and pre-event risk controls.
- Reuse `TimeSeries` endpoints (`get_quote_endpoint`, `get_daily_adjusted`, `get_market_status`) for underlying validation, VWAP backstops, and trading-session gating.

#### Historical Backfill Workflow
- Schedule a daily backfill job that calls `get_historical_options(symbol, date)` for any sessions missing in cold storage. The job iterates from the most recent missing day back to the 15-year AlphaVantage limit.
- Store results in S3/GCS partitioned by `symbol/date`, and register the location in the analytics catalog so the backtest layer can hydrate option chains without re-hitting the API.

#### Integration Hooks
- Publish normalized quotes onto the ingestion event bus (`ingestion.quotes.alpha_vantage`) for the analytics layer; include metadata about request latency, remaining quota, and data freshness.
- Emit heartbeat metrics (`alphavantage.latency_ms`, `alphavantage.calls_made`, `alphavantage.cache_hits`) to the monitoring subsystem to power the live dashboard health panel.

```python
# data_ingestion/alphavantage_client.py (sketch)
from alpha_vantage.options import Options
from alpha_vantage.techindicators import TechIndicators

class AlphaVantageClient:
    def __init__(self, api_key: str, rate_limiter, session_pool):
        self._options = Options(key=api_key, output_format='json')
        self._tech = TechIndicators(key=api_key, output_format='json')
        self._rate_limiter = rate_limiter
        self._session_pool = session_pool

    async def fetch_chain(self, symbol: str, contract: str | None = None) -> list[OptionQuote]:
        async with self._rate_limiter.reserve("REALTIME_OPTIONS"):
            raw = await self._session_pool.run(self._options.get_realtime_options, symbol, contract)
        return normalize_realtime_chain(raw)

    async def fetch_historical(self, symbol: str, date: date) -> list[OptionQuote]:
        async with self._rate_limiter.reserve("HISTORICAL_OPTIONS"):
            raw = await self._session_pool.run(self._options.get_historical_options, symbol, date.isoformat())
        return normalize_historical_chain(raw)

    async def fetch_indicators(self, symbol: str) -> IndicatorBundle:
        async with self._rate_limiter.reserve("MACD"):
            macd = await self._session_pool.run(self._tech.get_macd, symbol=symbol, interval='1min')
        async with self._rate_limiter.reserve("BBANDS"):
            bbands = await self._session_pool.run(self._tech.get_bbands, symbol=symbol, interval='1min', time_period=20)
        async with self._rate_limiter.reserve("VWAP"):
            vwap = await self._session_pool.run(self._tech.get_vwap, symbol=symbol, interval='1min')
        return normalize_indicators(macd, bbands, vwap)
```

### Interactive Brokers Real-time Data
**Repository**: https://github.com/ib-api-reloaded/ib_async
**Python Package**: `ib_async`

#### Ingestion Responsibilities
- Embed an `ib_async.IB` session wrapper inside `data_ingestion/ibkr_client.py` to expose async helpers for `reqMktData`, `reqTickByTickData`, `reqMarketDepth`, and `reqHistoricalData` (bars + option chains via `reqSecDefOptParams`).
- Maintain lightweight DTOs (`UnderlyingQuote`, `OrderBookSnapshot`, `TickEvent`) so analytics and execution modules consume normalized payloads rather than raw Interactive Brokers objects.
- Subscribe to gateway status feeds (managed accounts, portfolio updates, executions) to seed the risk and reporting layers with authoritative broker data.

#### Connection & Session Management
- Prefer `IB.connectAsync` with automatic reconnection/backoff from the repo; wrap it in a supervisor that restarts the session if heartbeats exceed a configurable threshold.
- Support both TWS (7497) and IB Gateway (4001) endpoints; expose entitlement toggles for delayed vs real-time market data (`reqMarketDataType`).
- Track client IDs per subsystem (ingestion, execution, monitoring) to avoid collisions; persist the next available ID in Redis so restarts remain deterministic.

#### Streaming & Historical Coverage
- Level 1 quotes: `reqMktData` for underlying equities/ETFs feeding the Greeks engine and hedging logic.
- Tick-by-tick: `reqTickByTickData` for trade/last/AllLast streams used in VPIN and microstructure analytics.
- Depth-of-market: `reqMarketDepth` with SMART depth aggregation to power the liquidity monitor; throttle to the broker’s 50-subscription limit.
- Option reference data: `reqSecDefOptParams` plus `reqContractDetails` to cross-check AlphaVantage chains and validate contract metadata before routing orders.
- Historical bars: asynchronous `reqHistoricalData` to backfill gaps (short-term hedging signals, VWAP sanity checks) when AlphaVantage latency/coverage lags.
- Histogram study support: `reqHistogramData` for intraday volume distributions to augment liquidity risk models.
- Fundamental & news feeds: `reqFundamentalData`, `reqNewsBulletins`, `reqNewsArticle`, and `reqNewsProviders` to give the AI overseer broker-sourced headlines and filings.
- Scanner APIs: `reqScannerSubscription` for dynamic watchlist refresh based on IB market scans (e.g., most active, high IV, gap movers).

#### Resilience & Compliance Hooks
- Leverage built-in `ib_async` disconnect/reconnect events; emit observability metrics (`ibkr.latency_ms`, `ibkr.reconnects`, `ibkr.market_data_blocks`) so the dashboard can flag degraded broker connectivity.
- Mirror raw ticks and order-book updates into an append-only Kafka/Redis Stream for audit; annotate each payload with the TWS/Gateway timestamp to reconcile against executed trades.
- Implement entitlement awareness (e.g., real-time vs frozen) and surface mismatches to the AI overseer so risk controls know when broker data is delayed.

#### Integration Flow
- Publish normalized IBKR events on `ingestion.quotes.ibkr` (L1/L2/ticks) and `ingestion.refdata.ibkr` (contract details) topics alongside AlphaVantage data for downstream fusion.
- Feed portfolio/account updates directly into `execution/position_manager.py` to keep positions in sync with the broker without additional polling.
- Record IBKR error codes/messages (e.g., 10167 market data permission) in the logging layer for rapid remediation.

#### Order Execution & Trade Lifecycle
- Utilize `ib_async.order` helpers (`MarketOrder`, `LimitOrder`, `StopOrder`, `StopLimitOrder`, `BracketOrder`) and `IB.bracketOrder` factory for automated OCO entry/exit logic.
- Support multi-leg strategies with `ComboLeg`, `Bag`, and `DeltaNeutralContract`; call `IB.qualifyContracts` before submission to populate conIds.
- Leverage `IB.placeOrder`, `IB.cancelOrder`, `IB.modifyOrder`, and `Trade` events (`orderStatusEvent`, `tradeUpdateEvent`) to drive our `order_manager.py` state machine.
- Integrate execution reports via `IB.reqExecutions` and `IB.execDetailsEvent` to reconcile fills and trigger AI overseer validation/audit logging.
- Apply risk controls by wiring `IB.globalCancel` and per-order `conditions` (price, time, margin) available in `ib_async.order` to emergency-stop workflows.

#### Account, Portfolio & Compliance Sync
- Subscribe to `IB.positions`, `IB.positionEvent`, `IB.accountSummary`, `IB.accountValue`, `IB.reqPnL`, and `IB.reqPnLSingle` to maintain real-time views for `position_manager.py` and `risk_manager.py`.
- Use `IB.managedAccounts` to map broker account codes into config-controlled strategy buckets.
- Pull daily statements and trade confirmations through `ib_async.flexreport` for long-term archival, complementing Redis snapshots.
- Exploit `IB.contractDetails` and `IB.securityDefinitionOptionalParameterEvent` to ensure every option order references an approved, active contract (expiry/strike validation).

#### Reference Patterns from Upstream Notebooks
- `notebooks/tick_data.ipynb`: async tick-by-tick ingestion with `reqTickByTickData`; adapt the Forex example to equities/ETFs for microstructure analytics.
- `notebooks/market_depth.ipynb`: demonstrates DOM subscription, event handling, and live order-book assembly—mirror this for our liquidity monitor service.
- `notebooks/bar_data.ipynb`: encapsulates paginated `reqHistoricalData` retrieval into pandas; re-use batching/pagination logic for overnight backfills and VWAP recomputation.

```python
# data_ingestion/ibkr_client.py (sketch)
from ib_async import IB, Stock

class IBKRClient:
    def __init__(self, host: str, port: int, client_id: int, loop):
        self._ib = IB()
        self._host = host
        self._port = port
        self._client_id = client_id
        self._loop = loop

    async def connect(self):
        await self._ib.connectAsync(self._host, self._port, clientId=self._client_id)

    async def stream_underlying(self, symbol: str):
        contract = Stock(symbol, 'SMART', 'USD')
        ticker = self._ib.reqMktData(contract, '', False, False)
        async for update in ticker.updateEvent.to_async_generator(self._loop):
            yield normalize_quote(symbol, update)

    async def stream_depth(self, contract, rows: int = 10):
        dom = self._ib.reqMarketDepth(contract, rows, isSmartDepth=True)
        async for update in dom.updateEvent.to_async_generator(self._loop):
            yield normalize_order_book(contract.symbol, update)

    async def fetch_hist_bars(self, contract, duration: str, bar_size: str):
        bars = await self._ib.reqHistoricalDataAsync(
            contract,
            endDateTime='',
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow='TRADES',
            useRTH=True,
        )
        return normalize_bars(contract.symbol, bars)
```

---

## 💾 Layer 2: Storage - Redis TimeSeries

### Redis TimeSeries Module
**Repository**: https://github.com/RedisTimeSeries/RedisTimeSeries
**Python Client**: https://github.com/RedisTimeSeries/redistimeseries-py

```yaml
# Local Redis Stack Docker
docker run -d --name redis-stack \
  -p 6379:6379 -p 8001:8001 \
  redis/redis-stack:latest

# Features:
- Automatic downsampling (1s → 1m → 5m → 1h → 1d)
- Compaction rules for OHLCV
- Millisecond precision timestamps
- Memory-optimized with automatic retention
```

---

## 📈 Layer 3: Analytics & Indicators

### Options Greeks Engine
**Repository**: https://github.com/vollib/py_vollib

#### Capabilities
- Supports Black, Black-Scholes, and Black-Scholes-Merton pricing models with analytical and numerical Greeks (Delta through Ultima) and robust implied-volatility inversion via Peter Jäckel’s `lets_be_rational` algorithm.
- Optional Numba acceleration (`py_vollib_vectorized`) unlocks batch evaluation across thousands of contracts—critical for 0DTE chains that need sub-second refreshes.
- Ships with reference pure-Python implementations for regression baselines, ensuring we can unit-test pricing edge cases independently of C extensions.

#### Integration Notes
- Wrap `py_vollib.black_scholes_merton.greeks.analytical` in `analytics/greeks_engine.py`, operating on the normalized `OptionQuote` DTO emitted by AlphaVantage/IBKR.
- Recompute implied vols via `py_vollib.black_scholes_merton.implied_volatility` when upstream Greeks disagree, and log any convergence failures for AI overseer review.
- Cache per-symbol term structures for risk-free rate and dividend yield, so repeated Greeks calls stay deterministic.

#### Performance Considerations
- Enable Numba where available (Apple Silicon, Linux servers) and gracefully degrade when not; fall back to reference Python for CI sanity checks.
- Batch requests per expiry/strike bucket to minimize Python overhead and reuse Vega/Volga outputs inside cross-asset stress testing.

#### Data Flow
```
OptionQuote (AlphaVantage/IBKR) → normalize_inputs()
  → implied_vol = BSM.implied_volatility(price, strike, rate, div, tenor)
  → greeks = BSM.greeks.analytical(greek_set, inputs, implied_vol)
  → publish `analytics.greeks.{symbol}` with payload {delta, gamma, vega, theta, vanna, volga, ...}
```

#### Configuration & Tuning
- `config/trading_params.yaml::greeks.refresh_ms` – cadence for recomputation per symbol/expiry.
- `config/trading_params.yaml::greeks.numba_enabled` – toggle JIT path (fallback to pure Python if false).
- `config/risk_limits.yaml::greeks.thresholds` – acceptable ranges for aggregate Delta/Vega before alerts.

#### Monitoring & Alerts
- Metrics: `greeks.compute_latency_ms`, `greeks.implied_vol_failures`, `greeks.numba_fallback_count`.
- Log anomalies when IV solver fails or when computed Greeks differ >`greeks.divergence_pct` from AlphaVantage-provided values.
- Dashboard tiles: per-symbol Delta/Vega, total portfolio Greeks, last refresh timestamp.

#### Module Interfaces
- Outputs: `GreeksSnapshot` DTO consumed by `signals/signal_generator.py`, `execution/portfolio_optimizer.py`, and `risk/risk_manager.py`.
- Inputs: `OptionQuote` DTOs from AlphaVantage/IBKR, rate/dividend curves from `storage/redis_timeseries.py`.
- Writes to Redis keys `greeks:{symbol}:{expiry}` with TTL aligned to refresh cadence.

### Volatility Regime Classification
**Repository**: https://github.com/hmmlearn/hmmlearn

#### Model Architecture
- Use `hmmlearn.hmm.GaussianHMM` for a three-state regime engine (Calm, Elevated, Stressed); fall back to `GMMHMM` when multimodal emissions improve fit.
- Leverage `CategoricalHMM` for event-driven state tracking (FOMC, CPI) and fuse with Gaussian regimes during AI overseer narratives.
- Apply `partial_fit` for online updates so intraday shifts can adjust transition matrices without full retraining.

#### Pipeline Integration
- Train offline with AlphaVantage/IBKR history, stash `startprob_`/`transmat_` snapshots in Redis, and warm start at boot.
- Expose posterior probabilities and Viterbi state labels through `regime_classifier.py` for downstream signal gating.
- Monitor `ConvergenceMonitor` output and trigger fallback to prior parameters if EM stalls before tolerance.

#### Monitoring & Retraining
- Schedule nightly or event-triggered retrains; compare log-likelihood deltas and alert when model drift exceeds tolerance.
- Version regimes (UUID + model hash) so risk reports can cite which parameter set approved a trade.

#### Data Flow
```
FeatureVector (realized_vol, vpin, stress, macro) → scale() →
  regime_model.predict_proba() → posterior_probs
  regime_model.decode() → viterbi_state
  emit `regime.state` event with {posterior, state, timestamp}
```

#### Configuration & Tuning
- `config/ai_config.yaml::regime.states` – number and labels of regimes.
- `config/ai_config.yaml::regime.retrain_cron` – cron expression for full EM retrain.
- `config/ai_config.yaml::regime.probability_thresholds` – gating thresholds for signal attenuation.
- `config/ai_config.yaml::regime.partial_fit_window` – number of recent observations used for incremental updates.

#### Monitoring & Alerts
- Metrics: `regime.log_likelihood`, `regime.posterior_entropy`, `regime.partial_fit_latency_ms`.
- Alert when `posterior_max < min_confidence` for N consecutive windows or when `log_likelihood_delta < drift_tol`.
- Dashboard widget: current state, probability distribution, time since last retrain.

#### Module Interfaces
- Outputs: `RegimeAssessment` consumed by `signals/signal_generator.py` (signal strength scaling) and `ai_overseer/market_analyst.py` (narratives).
- Inputs: Feature vectors aggregated by `analytics/liquidity_monitor.py`, `analytics/vpin_calculator.py`, and macro overlay.
- Registers state history in Redis key `regime:timeline` for audit and backtests.

### Liquidity Stress Index
**Repository**: https://github.com/orderbooktools/crobat

#### Core Features
- Crobat captures Level 2 order-book snapshots, signed LO/CO/MO event streams, and price ladders following modern microstructure conventions.
- Includes utilities for order flow imbalance (OFI), market depth analytics, and export pipelines (CSV/Parquet, Grafana dashboards).
- Demonstrates async ingestion patterns suitable for high-throughput crypto/equity venues—adaptable to IBKR DOM feeds.

#### Integration Strategy
- Mirror Crobat’s signed depth schema inside `analytics/liquidity_monitor.py` so stress metrics align with academic definitions.
- Blend OFI, spread width, queue depletion, and `reqHistogramData` volume to compute a 0–100 stress score powering the dashboard.
- Archive DOM snapshots for anomaly detector training and compliance replay.

#### Operational Notes
- Keep depth subscriptions within IBKR limits (≤50); dynamically throttle low-liquidity symbols as Crobat suggests.
- Surface dropped DOM updates via observability to avoid silent liquidity blind spots.

#### Data Flow
```
DOMUpdate (IBKR) → map_to_signed_depth() →
  update_depth_matrix(symbol, level)
  compute_metrics({spread, depth_ratio, OFI, queue_depletion})
  liquidity_score = weighted_sum(metrics)
  publish `liquidity.stress.{symbol}`
```

#### Configuration & Tuning
- `config/trading_params.yaml::liquidity.depth_levels` – number of DOM levels captured per side.
- `config/trading_params.yaml::liquidity.metric_weights` – weights for spread/OFI/queue depletion in stress computation.
- `config/trading_params.yaml::liquidity.alert_thresholds` – stress score cutoffs (e.g., 60 warning, 80 critical).
- `config/system_config.yaml::dom_snapshot_retention_days` – archival window for raw snapshots.

#### Monitoring & Alerts
- Metrics: `liquidity.stress_score`, `liquidity.dom_gap_count`, `liquidity.snapshot_latency_ms`.
- Alerts: trigger when stress score exceeds thresholds or when DOM update gap >`dom_gap_sec`.
- Dashboard: heatmap of stress by symbol, top deteriorating names, DOM depth trend.

#### Module Interfaces
- Outputs: `LiquidityStressSnapshot` consumed by `signals/signal_generator.py` (trade veto) and `risk_manager.py` (position sizing caps).
- Inputs: DOM/Tick events from IBKR ingestion, historical depth from Redis TS.
- Stores per-symbol states in `liquidity:{symbol}` streams for AI anomaly detector training.

### VPIN Order Flow Toxicity
**Repository**: https://github.com/yt-feng/VPIN

#### Methodology
- Implements volume-synchronized bucket construction (default 50), buy/sell imbalance calculation, and VPIN toxicity outputs illustrated in the accompanying notebook.
- Provides visual benchmarks linking VPIN spikes to price dislocations; useful for calibrating alert thresholds.

#### System Application
- Embed the VPIN logic within `analytics/vpin_calculator.py`, parameterizing bucket count/volume to suit each symbol’s liquidity profile.
- Persist partial bucket state in Redis so restarts resume without losing accumulated volume.
- Emit raw VPIN plus z-scored/rolling statistics, triggering liquidity alerts when toxicity breaches configured limits.

#### Data Flow
```
TickEvent (price, size, side) → append_to_bucket()
  if bucket_volume >= VBS:
      compute_imbalance()
      update_vpin_series()
      rotate_bucket(residual_volume)
  publish `vpin.value` + diagnostics
```

#### Configuration & Tuning
- `config/trading_params.yaml::vpin.bucket_count` – number of volume buckets (default 50).
- `config/trading_params.yaml::vpin.target_volume` – target volume per bucket per symbol.
- `config/trading_params.yaml::vpin.alert_levels` – toxicity thresholds tied to liquidity alerts.
- `config/system_config.yaml::vpin.persistence` – Redis keys for partial bucket snapshots and retention length.

#### Monitoring & Alerts
- Metrics: `vpin.current`, `vpin.bucket_fill_pct`, `vpin.volume_processed`.
- Alert when VPIN > threshold or when bucket fill stalls (no rotation within `max_idle_minutes`).
- Dashboard tiles: VPIN trend, correlation with realized volatility, bucket fill status.

#### Module Interfaces
- Outputs feed `liquidity_monitor.py` (combined stress score), `regime_classifier.py` (feature), and AI overseer alerts.
- Inputs: tick stream from IBKR and historical data for backfill from AlphaVantage.
- Stores computed series under `vpin:{symbol}` for backtests and compliance review.

### Macro Economic Overlay
**Repository**: https://github.com/JerBouma/FinanceToolkit

#### Data Coverage
- FinanceToolkit exposes 150+ ratios, macro indicators, performance metrics, and option analytics across equities, ETFs, FX, crypto, commodities, and economic series via FinancialModelingPrep.
- Supports flexible frequencies (`intraday` to `annual`) and includes higher-level models (Altman Z, WACC, DuPont, VaR, Sharpe/Sortino).

#### Integration Plan
- Schedule Toolkit jobs to pull macro series (GDP, CPI, FFR, unemployment, yields) plus company ratios for watchlist symbols; cache in Redis/S3 for reuse.
- Feed composite risk scores into `analytics/macro_overlay.py` and AI overseer narratives (e.g., debt ratios, profitability trends).
- Implement graceful degradation when API quotas are hit by computing fallback ratios from stored financial statements.

#### Automation Hooks
- Monitor API authentication/usage separately from AlphaVantage/IBKR keys, since the Toolkit depends on FinancialModelingPrep entitlements.
- Persist outputs to Parquet partitioned by indicator/country so the backtest engine can replay macro contexts.

#### Data Flow
```
scheduler (cron) → Toolkit.fetch(indicators, tickers)
  → normalize_frequency()
  → compute_composites(Z-scores, AltmanZ, WACC)
  → publish `macro.overlay` payload with risk scores + narratives inputs
```

#### Configuration & Tuning
- `config/macro_overlay.yaml::indicators` – list of economic series and frequency.
- `config/macro_overlay.yaml::composite_weights` – weights for composite risk score (growth, inflation, rates).
- `config/macro_overlay.yaml::refresh_cron` – schedule for pulls (e.g., daily 06:00 ET).
- `config/macro_overlay.yaml::api_keys.financial_modeling_prep` – entitlement storage.

#### Monitoring & Alerts
- Metrics: `macro.fetch_duration_ms`, `macro.api_quota_remaining`, `macro.data_staleness_hours`.
- Alert when data staleness exceeds configured max or API quota < reserve threshold.
- Dashboard cards: current macro composite score, key indicator deltas, last successful refresh.

#### Module Interfaces
- Outputs consumed by `regime_classifier.py` (feature vector), `ai_overseer/market_analyst.py` (narratives), and `signals/signal_generator.py` (bias adjustments).
- Inputs: FinanceToolkit API plus cached financial statements in storage.
- Writes to Redis hashes `macro:{indicator}` and S3 `macro/year=.../indicator=...` partitions.

### Microstructure Analytics
**Repository**: https://github.com/orderbooktools/crobat (baseline) + IBKR tick/DOM APIs

#### Focus Areas
- Repurpose Crobat’s event labelling to classify IBKR ticks into LO/CO/MO flows; derive queue position, spread moves, and signed order imbalance features.
- Estimate realized slippage by pairing execution timestamps with DOM state, capturing queue latency and sweep detection.
- Provide microsecond-level signals (quote stability, cancellation bursts) that gate signal execution or trigger AI anomaly alerts.

#### Implementation Notes
- Keep feature extraction stateless—derive from Redis-stored DOM snapshots and execution logs so modules remain loosely coupled.
- Persist feature vectors to cold storage for offline model training (anomaly detector, AI explanations) and dashboard drill-downs.
- Align schemas with Crobat/Grafana expectations to reuse existing visualization components.

#### Data Flow
```
TickEvent + DOMSnapshot + ExecutionReport → build_feature_vector()
  features = {queue_pos, spread_change, cancel_rate, sweep_flag, slippage}
  write to Redis Stream `micro.{symbol}`
  forward to anomaly_detector & signal_validator
```

#### Configuration & Tuning
- `config/microstructure.yaml::feature_window_ms` – lookback window for cancellation/imbalance calculations.
- `config/microstructure.yaml::slippage_bands` – thresholds for acceptable realized slippage.
- `config/microstructure.yaml::anomaly_thresholds` – z-score cutoffs for triggering AI alerts.

#### Monitoring & Alerts
- Metrics: `micro.cancel_rate`, `micro.queue_drop_pct`, `micro.slippage_bp`.
- Alerts when slippage exceeds bands or queue depletion persists beyond `queue_alert_duration`.
- Dashboard: scatterplots of slippage vs liquidity stress, heatmap of anomaly counts, real-time queue position charts.

#### Module Interfaces
- Outputs consumed by `signals/signal_validator.py` (trade veto), `ai_overseer/anomaly_detector.py`, and `execution/risk_manager.py`.
- Inputs from IBKR tick feed, DOM snapshots, execution logs (fills, order status).
- Archives to Parquet `microstructure/date=symbol=` for compliance forensics.

### Risk Attribution (PCA)
**Repository**: https://github.com/DavidCico/Factor-risk-model-with-principal-component-analysis

#### Model Capabilities
- Applies PCA to security return series to derive orthogonal risk factors, mapping securities to factors via regression and exporting coefficients (`pcaMappingsResults.csv`).
- Includes exponentially weighted VaR calculations (`var_exp_weighted.py`) and data ingestion scripts for NASDAQ/S&P universes via Yahoo Finance.

#### Integration Strategy
- Port the PCA workflow to `analytics/risk_attribution.py`, using our stored underlying returns plus macro factors to compute daily loadings and explained variance.
- Combine PCA outputs with FinanceToolkit metrics to label latent components (growth, rates, credit) for AI narratives.
- Feed factor exposures into risk dashboards and position sizing logic (e.g., cap exposure to first eigenfactor).

#### Operational Considerations
- Recompute monthly with rolling windows, alerting if cumulative explained variance falls below thresholds (e.g., 70%).
- Archive factor loadings, VaR metrics, and residuals to Parquet for audit/backtest reproducibility.

#### Data Flow
```
ReturnMatrix (symbols × dates) → demean/standardize →
  PCA.fit(window) → eigenvectors, eigenvalues
  factor_loadings = transform(returns)
  residuals = returns - inverse_transform(factors)
  publish `risk.factors` + `risk.residuals`
```

#### Configuration & Tuning
- `config/risk_model.yaml::pca.window_days` – rolling window length for PCA.
- `config/risk_model.yaml::pca.num_factors` – max factors to retain.
- `config/risk_model.yaml::pca.min_explained_variance` – alert threshold.
- `config/risk_model.yaml::var.lambda` – decay factor for EW VaR supplement.

#### Monitoring & Alerts
- Metrics: `risk.pca.explained_variance`, `risk.pca.residual_vol`, `risk.pca.model_age_days`.
- Alert when explained variance < threshold or residual volatility spikes >`residual_alert_pct`.
- Dashboard: factor exposure bar charts, variance explained timeline, top contributors per factor.

#### Module Interfaces
- Outputs consumed by `risk_manager.py` (factor limits), `portfolio_optimizer.py` (hedge suggestions), and AI overseer (risk narratives).
- Inputs from storage (cached returns, macro factors), FinanceToolkit metrics.
- Persist results to Redis hash `risk:pca:{date}` and S3 `risk_pca/` for reproducibility.

---

## 🎯 Layer 4: Signal Generation & Backtesting

### Primary Framework - Zipline (Advanced Analytics Priority)
**Repository**: https://github.com/stefan-jansen/zipline-reloaded

#### Capabilities
- Event-driven backtester with built-in order simulation (slippage, commissions), asset pipeline, and exchange calendar support.
- Supports both algorithmic scripts and notebook workflows; integrates naturally with Pandas and pipeline factors.
- Extensible data bundles for custom datasets (options, macro series) via `zipline ingest` hooks.

#### Data Flow
```
HistoricalBundle (pricing, fundamentals) → bundle ingest
  → zipline.run_algorithm(initial_capital, start, end, handle_data)
  → pipeline factors & signals execute
  → orders simulated → performance DataFrame
  → persist to `backtests/{id}/performance.pkl`
```

#### Configuration & Tuning
- `config/backtest.yaml::zipline.bundle` – selects data bundle (Quandl, custom Redis extract).
- `config/backtest.yaml::zipline.calendar` – trading calendar (NYSE, CME, etc.).
- `config/backtest.yaml::zipline.capital_base` – initial capital per strategy.
- `config/backtest.yaml::zipline.slippage` / `commission` – models and parameters for trade simulation.
- `config/backtest.yaml::zipline.pipeline_chunks` – lookback windows for factor computation.

#### Monitoring & Alerts
- Metrics: `backtest.runtime_sec`, `backtest.order_count`, `backtest.max_drawdown`, `backtest.alpha_ic`.
- Emit run status to observability (`backtest.status` gauge) and alert on failures or runtime exceeding `runtime_budget`.
- Dashboard: run queue status, P&L curves, factor exposures during simulation.

#### Module Interfaces
- Inputs: curated historical datasets from `storage/data_persistence.py`, factor definitions shared with live signal engine.
- Outputs: performance tears (`performance.pkl`, `transactions.pkl`) piped to Pyfolio; factor returns exported to Alphalens.
- Backtest IDs registered in Redis `backtest:index` for AI overseer review and QA sign-off.

### Factor Analysis - Alphalens
**Repository**: https://github.com/quantopian/alphalens

#### Capabilities
- Generates factor tear sheets with returns analysis, information coefficients, turnover, and sector stratification.
- Works directly with Zipline pipeline output (factor values, forward returns) and supports quantile bucketing.

#### Data Flow
```
factor_series (Zipline pipeline) + pricing_panel → alphalens.utils.get_clean_factor_and_forward_returns()
  → alphalens.tears.create_full_tear_sheet()
  → export plots + tables to `reports/factors/{factor}/{timestamp}`
```

#### Configuration & Tuning
- `config/backtest.yaml::alphalens.quantiles` – number of buckets for factor evaluation.
- `config/backtest.yaml::alphalens.periods` – forward return horizons (1D, 5D, 21D).
- `config/backtest.yaml::alphalens.groupby` – sector/industry mapping for grouped analysis.
- `config/backtest.yaml::alphalens.ic_thresholds` – alerting bounds for IC significance.

#### Monitoring & Alerts
- Metrics: `alphalens.ic_mean`, `alphalens.ic_ir`, `alphalens.turnover_pct`.
- Alert when IC drops below threshold for consecutive windows or when quantile returns invert (Q1 outperforming Q5).
- Dashboard: factor IC trends, quantile returns heatmap, turnover table.

#### Module Interfaces
- Consumes: factor outputs from Zipline pipeline or live signal generator.
- Produces: summary JSON/CSV consumed by AI overseer (factor health narratives) and by risk team for validation.
- Artifacts stored in S3 `factor_tears/` and linked within reporting module.

### Performance & Risk Analysis - Pyfolio
**Repository**: https://github.com/quantopian/pyfolio

#### Capabilities
- Generates comprehensive performance tear sheets (returns, drawdown, exposures, stress tests) from backtest or live results.
- Calculates risk ratios (Sharpe, Sortino, max drawdown), rolling statistics, and event studies.

#### Data Flow
```
performance_df (Zipline output) + benchmark_series → pyfolio.timeseries returns
  → pyfolio.tears.create_full_tear_sheet()
  → save HTML/PDF to `reports/performance/{strategy}/{run_id}`
```

#### Configuration & Tuning
- `config/backtest.yaml::pyfolio.benchmark` – benchmark symbol/series for relative metrics.
- `config/backtest.yaml::pyfolio.risk_free_rate` – per-period risk-free assumption.
- `config/backtest.yaml::pyfolio.event_windows` – lookback/forward windows for event analysis.
- `config/backtest.yaml::pyfolio.outlier_threshold` – winsorization limits on returns series.

#### Monitoring & Alerts
- Metrics: `pyfolio.sharpe`, `pyfolio.sortino`, `pyfolio.max_drawdown`, `pyfolio.cagr`.
- Alert on drawdown exceeding `max_drawdown_limit` or Sharpe dropping below strategy mandate.
- Dashboard: cumulative returns, drawdown curve, rolling beta/volatility.

#### Module Interfaces
- Inputs: performance streams from Zipline backtests and live trading logs.
- Outputs: risk summaries consumed by `ai_overseer/trade_validator.py` and `reporting/report_generator.py`.
- Stores summary stats in Redis `performance:{strategy}` for quick retrieval in dashboards.

---

## ⚡ Layer 5: Execution

### Order Management System
**Repository**: https://github.com/ib-api-reloaded/ib_async

#### Capabilities
- Centralizes order creation, amendment, and cancellation with support for market, limit, stop, stop-limit, and bracket orders (parent/child OCO) leveraging `ib_async.order` helpers.
- Manages per-symbol execution queues to serialize submissions and respect IBKR pacing violations while still handling concurrent symbols.
- Tracks order state transitions (`PreSubmitted`, `Submitted`, `Filled`, `Cancelled`, `Inactive`) and reconciles with broker fills in sub-second latency.

#### Data Flow
```
SignalDecision → order_manager.create_order()
  → pre-trade checks (risk flags, throttle, duplicate detection)
  → translate to IBKR contract/order (qualifyContracts, bracketOrder)
  → ib_async.IB.placeOrder(contract, order)
  → execution events → order_manager.handle_fill()
  → publish `execution.fills` + update position manager
```

#### Configuration & Tuning
- `config/execution.yaml::order_manager.client_ids` – reserved client IDs per subsystem (ingestion, execution, monitoring).
- `config/execution.yaml::order_manager.max_orders_per_second` – pacing guard to prevent IBKR error 10147.
- `config/execution.yaml::order_manager.retry_policy` – backoff strategy for transient errors (network, pacing).
- `config/execution.yaml::order_manager.time_in_force` – defaults per strategy (DAY, IOC, GTC).
- `config/execution.yaml::routing.smart_enabled` – toggle SMART routing vs directed exchanges.

#### Monitoring & Alerts
- Metrics: `execution.orders_submitted`, `execution.fills`, `execution.rejects`, `execution.latency_ms`, `execution.retry_count`.
- Alert on consecutive rejects (`execution.reject_streak`) or when average latency > `latency_budget_ms` for defined window.
- Dashboard: live order blotter (status, price, size), pacing gauge, reject heatmap by reason code.

#### Module Interfaces
- Inputs: validated signals from `signals/signal_validator.py`, position limits from `risk_manager.py`.
- Outputs: order/fill events to `execution/position_manager.py`, `analytics/microstructure.py`, and audit bus (`execution.audit` stream).
- Stores order metadata in Redis hash `orders:{order_id}` with cross-references to strategy and AI oversight decisions.

#### Resilience & Failover
- Heartbeat watchers monitor IBKR connection; auto-suspend new orders and page ops if `ib_async` disconnects beyond `disconnect_grace_seconds`.
- Persist in-flight orders to disk (append-only log) so restarts can resubscribe to `IB.execDetailsEvent` and sync state.
- Support manual kill-switch via `execution_control.shutdown` flag in Redis.

### Portfolio Optimizer & Sizing
**Module**: `execution/portfolio_optimizer.py`

#### Capabilities
- Converts signal scores and Greeks into executable order quantities using Kelly-like scaling, volatility targeting, and position concentration constraints.
- Supports scenario-aware sizing (stress-adjusted exposures, liquidity caps) and returns target order list to the order manager.

#### Data Flow
```
SignalSet (direction, conviction, target_greeks) + current_positions + risk_limits
  → optimizer.compute_target_weights()
  → translate to share/contract quantities (round lot aware)
  → hand off to order_manager.submit_batch()
```

#### Configuration & Tuning
- `config/execution.yaml::optimizer.vol_target` – annualized vol target per strategy.
- `config/execution.yaml::optimizer.greeks_limits` – max Delta/Vega per symbol and portfolio.
- `config/execution.yaml::optimizer.liquidity_cap` – % of ADV or quote size to respect when sizing.
- `config/execution.yaml::optimizer.rounding` – contract rounding rules (e.g., nearest 1 contract for options).

#### Monitoring & Alerts
- Metrics: `optimizer.target_gross_exposure`, `optimizer.turnover`, `optimizer.size_reduction_pct` (due to risk caps).
- Alert when requested size is slashed >`size_cut_threshold` or when optimizer fails to converge.
- Dashboard: target vs actual exposure, constraint binding diagnostics, trade size distribution.

#### Module Interfaces
- Consumes: signals, current portfolio state (`position_manager`), risk constraints (`risk_manager`), market data (bid/ask, ADV) from analytics layer.
- Produces: normalized order intents (symbol, quantity, limit price hints) for `order_manager`.
- Persists optimization decisions to `optimizer:decisions:{timestamp}` for audit and AI explanation.

---

## 🛡️ Layer 6: Position Management & Risk

### Position & Risk Framework

#### Capabilities
- Maintains authoritative view of all open option positions, realized/unrealized P&L, and Greeks exposures in sync with IBKR via position and execution streams.
- Applies risk controls: trailing stops, tiered take profits, hard stop-loss, time-based exits, option-specific theta management, and dynamic heat maps.
- Computes portfolio metrics (VaR/CVaR, beta/gamma exposure, max drawdown) and enforces per-symbol and portfolio limits in real time.

#### Data Flow
```
execution.fill_event → position_manager.update_position()
  → recalc Greeks & P&L using `analytics/greeks_engine`
  → evaluate risk rules (trailing stop, take profit, time exit)
  → trigger actions (adjust stop, send close order)
  → publish `positions.state` snapshot + risk metrics
```

#### Configuration & Tuning
- `config/risk_limits.yaml::positions.symbol_limits` – max position size/Delta/Vega per ticker and expiry bucket.
- `config/risk_limits.yaml::positions.trailing_stop` – enable flag, percentage/dollar value, activation criteria.
- `config/risk_limits.yaml::positions.take_profit_levels` – tiers (target %, size to trim).
- `config/risk_limits.yaml::positions.stop_loss_pct` – hard stop thresholds.
- `config/risk_limits.yaml::positions.time_exit_minutes` – time buffers for 0DTE/1DTE exits before market close.
- `config/risk_model.yaml::var.parameters` – VaR lookback window, confidence level, decay.

#### Monitoring & Alerts
- Metrics: `positions.net_delta`, `positions.net_vega`, `positions.gross_exposure`, `positions.pnl_realized`, `positions.pnl_unrealized`, `positions.var_95`.
- Alert when exposure breaches limits, when trailing stops fire, or when VaR exceeds tolerance.
- Dashboard: current positions blotter (symbol, strike, DTE, P&L), risk heat map, stop/TP status, VaR trend.

#### Module Interfaces
- Inputs: fills from `order_manager`, live prices from AlphaVantage/IBKR, Greeks from analytics layer.
- Outputs: position snapshots to `risk_manager.py`, AI overseer (for override queue), reporting layer (daily statements).
- Stores state in Redis `positions:{symbol}` plus append-only ledger for compliance (multi-year retention).

#### Resilience & Audit Trail
- Persist full trade ledger and daily position snapshots to cold storage (S3/GCS) with retention policy (minimum 7 years).
- On restart, replay ledger and reconcile with IBKR `positions()` and `executions()` to ensure parity.
- Tag every risk action (stop triggered, forced exit) with unique ID and capture context for AI override workflow.

### MOC Imbalance Predictor

#### Capabilities
- Predicts market-on-close (MOC) imbalance direction/magnitude using historical auction data, intraday order flow, and volume profiles to inform late-day hedging and exits.
- Generates probability-weighted signals (buy/sell/neutral) and expected imbalance size for relevant symbols (index ETFs, high-volume components).

#### Data Flow
```
IntradayFeatures (order flow, volume profile, VPIN, macro) + historical auction dataset → feature_engineering()
  → model.predict_proba() (XGBoost/LightGBM)
  → output {direction, size, confidence}
  → feed into position_manager & signal generator for MOC adjustments
```

#### Configuration & Tuning
- `config/risk_model.yaml::moc.training_window_days` – history depth for retraining.
- `config/risk_model.yaml::moc.refresh_cron` – schedule for model retrain (e.g., weekly).
- `config/risk_model.yaml::moc.thresholds` – confidence cutoffs for action (e.g., >0.7 to hedge).
- `config/risk_model.yaml::moc.symbols` – watchlist for imbalance modeling.
- `config/risk_model.yaml::moc.features` – toggle inclusion of VPIN, macro, or cross-asset stress features.

#### Monitoring & Alerts
- Metrics: `moc.prediction_confidence`, `moc.direction_accuracy` (tracked post-close), `moc.hedge_notional`.
- Alert when model confidence remains low for N days (potential data drift) or when realized imbalance diverges significantly from forecast.
- Dashboard: daily imbalance predictions vs realized, accuracy heatmap by symbol, cumulative P&L from MOC hedging.

#### Module Interfaces
- Consumes: intraday analytics (VPIN, liquidity stress), AlphaVantage macro overlay, IBKR auction data feed.
- Produces: imbalance advisories to `signals/signal_generator.py`, position manager (pre-close adjustments), and AI overseer (explainability).
- Stores model artifacts and feature data in `models/moc/` with versioned metadata for audit.

---

## 🤖 Layer 7: AI Overseer Integration

### Claude AI Integration (Primary)
**Repository**: Custom implementation using Anthropic API

#### Capabilities
- Acts as the final AI validator for trade decisions, risk narratives, and anomaly explanations using Anthropic Claude models.
- Provides natural-language rationales, highlights conflicting signals, and escalates ambiguous cases to human override queue.
- Generates daily market commentary blending regime probabilities, macro overlay, and microstructure alerts.

#### Data Flow
```
TradeProposal / RiskEvent / AnomalyFeature → prompt_builder.compose()
  → AnthropicClaudeClient.invoke(model, prompt, tools)
  → parse response {verdict, rationale, confidence, actions}
  → update execution/AI override queue + log to audit trail
```

#### Configuration & Tuning
- `config/ai_config.yaml::claude.api_key` – Anthropic API credential.
- `config/ai_config.yaml::claude.model` – model selection (e.g., claude-3-opus).
- `config/ai_config.yaml::claude.decision_threshold` – confidence required to auto-approve trades.
- `config/ai_config.yaml::claude.override_window_minutes` – human override SLA before decision auto-executes.
- `config/ai_config.yaml::claude.prompt_templates` – template IDs for trade, risk, macro narratives.

#### Monitoring & Alerts
- Metrics: `ai.claude.calls`, `ai.claude.latency_ms`, `ai.claude.approval_rate`, `ai.claude.escalations`, `ai.claude.override_rate`.
- Alert if API latency exceeds threshold, error rate spikes, or override backlog surpasses limit.
- Dashboard: decision queue status, approvals vs rejects, rationale snippets, SLA countdown timers.

#### Module Interfaces
- Inputs: trade intents from `order_manager`, risk alerts from `position_manager`, anomaly summaries from `ai_overseer/anomaly_detector.py`.
- Outputs: approve/reject decisions to execution layer, narrative text to reporting/social modules, escalation tasks to human console.
- Persist transcripts to S3 `ai_logs/claude/{date}` and index metadata in Redis `ai:claude:decisions` for compliance.

### OpenAI GPT-4 (Backup/Complement)
**Repository**: https://github.com/openai/openai-python

#### Capabilities
- Provides complementary analysis: technical pattern summaries, news sentiment, multimodal chart interpretation using GPT-4 and GPT-4V.
- Serves as fallback validator when Claude unavailable; cross-checks narratives for consistency.

#### Data Flow
```
ContentRequest (news digest, chart PNG, factor summary) → openai_client.invoke(model, prompt)
  → response text/assets → downstream consumers (reporting, social bots)
```

#### Configuration & Tuning
- `config/ai_config.yaml::openai.api_key` – OpenAI credential.
- `config/ai_config.yaml::openai.models` – mapping for text vs vision tasks.
- `config/ai_config.yaml::openai.rate_limits` – concurrency controls to respect quota.
- `config/ai_config.yaml::openai.sentiment_thresholds` – classification cutoffs for bullish/bearish flags.

#### Monitoring & Alerts
- Metrics: `ai.openai.calls`, `ai.openai.latency_ms`, `ai.openai.error_rate`, `ai.openai.sentiment_score`.
- Alert on quota exhaustion or high error rate; dashboard shows sentiment timeline, news coverage diversity.

#### Module Interfaces
- Inputs: news feeds, price charts, factor data; optionally hand-offs from Claude when additional context needed.
- Outputs: annotated summaries to reporting/social modules and AI oversight log.
- Stores responses in `ai_logs/openai/` with references for compliance review.

### Specialized Quant AI (mlfinlab)
**Repository**: https://github.com/hudson-and-thames/mlfinlab

#### Capabilities
- Supplies advanced microstructure features, labeling algorithms (triple-barrier, meta-labeling), and feature importance tools for strategy diagnostics.
- Supports regime/alpha model training loops and dataset curation.

#### Data Flow
```
LabeledData (ticks, features) → mlfinlab.labeling.apply_triple_barrier()
  → feature_engineering (microstructure features)
  → model training/evaluation
  → send feature importance / diagnostics to AI overseer + signal research
```

#### Configuration & Tuning
- `config/ai_config.yaml::mlfinlab.labeling` – barrier multipliers, holding periods.
- `config/ai_config.yaml::mlfinlab.feature_set` – toggle which microstructure metrics feed models.
- `config/ai_config.yaml::mlfinlab.backtest_window` – lookback for recalibrating models.

#### Monitoring & Alerts
- Metrics: `ai.mlfinlab.model_accuracy`, `ai.mlfinlab.feature_importance_shift`, `ai.mlfinlab.training_runtime`.
- Alert when accuracy drifts below threshold or feature importance shifts drastically (possible data leak/drift).
- Dashboard: feature importance heatmaps, ROC curves, label distribution.

#### Module Interfaces
- Feeds strategy research, AI overseer validation rules, and anomaly detection calibrations.
- Consumes data from storage/analytics; outputs stored in `models/mlfinlab/` with metadata for reproducibility.

### Anomaly Detection (pyod)
**Repository**: https://github.com/yzhao062/pyod

#### Capabilities
- Runs ensemble of 30+ outlier detection algorithms on microstructure, execution, and risk metrics to flag unusual behavior.
- Streams anomaly scores to AI overseer for interpretation and to risk dashboards for visibility.

#### Data Flow
```
FeatureVector (microstructure, execution latency, liquidity stress) → pyod.detector.predict_proba()
  → anomaly_score
  → thresholding & aggregation → alert bus + AI explainability
```

#### Configuration & Tuning
- `config/ai_config.yaml::pyod.models` – selected detectors (e.g., HBOS, IsolationForest, AutoEncoder).
- `config/ai_config.yaml::pyod.thresholds` – anomaly score cutoffs per feature group.
- `config/ai_config.yaml::pyod.retrain_cron` – schedule for detector retraining/refresh.
- `config/ai_config.yaml::pyod.window_size` – rolling window for normalization.

#### Monitoring & Alerts
- Metrics: `ai.anomaly.count`, `ai.anomaly.score_avg`, `ai.anomaly.false_positive_rate` (verified post-mortem).
- Alert when anomaly count surges or when detectors disagree significantly (consensus breakdown).
- Dashboard: anomaly timeline, top contributing features, drill-down into raw events.

#### Module Interfaces
- Inputs: features from analytics, execution, positions; normalization stats from storage.
- Outputs: flagged events to AI overseer (for narrative) and risk manager (for potential halts).
- Stored in `ai/anomaly_events/` with context for compliance and model recalibration.

---

## 📊 Layer 8: Report Generation

### PDF Report Engine
**Repository**: https://github.com/py-pdf/fpdf2

#### Capabilities
- Produces branded PDF packs (daily ops, weekly investor, monthly compliance) with modular sections, tables, and embedded visuals.
- Supports pagination, table-of-contents, footnotes, and watermarking for compliance distribution.
- Handles multi-audience customization (retail vs institutional) via template variants.

#### Data Flow
```
ReportRequest → collect data (performance, positions, AI narratives, macro)
  → render charts (Visualization Suite)
  → template_engine.merge(sections)
  → fpdf2 compose → PDF bytes
  → deliver (S3 upload, email, social broadcast)
```

#### Configuration & Tuning
- `config/reporting.yaml::pdf.templates` – template definitions, branding assets, section ordering.
- `config/reporting.yaml::pdf.schedules` – cron expressions per report cadence.
- `config/reporting.yaml::pdf.delivery_channels` – email lists, Telegram/Discord rooms, S3 targets.
- `config/reporting.yaml::pdf.retention_days` – archive retention for compliance.
- `config/reporting.yaml::pdf.page_limits` – guardrails for maximum length.

#### Monitoring & Alerts
- Metrics: `report.pdf.generate_ms`, `report.pdf.size_kb`, `report.pdf.failures`, `report.pdf.delivery_latency`.
- Alert on generation failures, oversized PDFs, or delivery errors.
- Dashboard: recent report status, generation time trend, distribution success heatmap.

#### Module Interfaces
- Inputs: Pyfolio performance summaries, position/risk snapshots, AI narratives, macro overlay.
- Outputs: PDF artifacts in `reports/pdf/{date}/{report}.pdf`, metadata published to Redis `reports:latest`, triggers to social broadcaster.
- Stores audit metadata (data sources, version hashes) for compliance review.

### Visualization Suite
**Plotly**: https://github.com/plotly/plotly.py (interactive charts)
**Matplotlib**: https://github.com/matplotlib/matplotlib (publication quality)

#### Capabilities
- Generates both interactive dashboards (Plotly HTML) and static images (Matplotlib/Plotly static) for embedding in reports, dashboards, and social posts.
- Offers reusable chart builders: performance, drawdown, exposure, Greeks, liquidity, anomaly counts.

#### Data Flow
```
ChartRequest (type, data_source, audience) → load data → apply styling/theme → render
  → export PNG/SVG/HTML
  → return asset handle (path/URL) to caller
```

#### Configuration & Tuning
- `config/reporting.yaml::visual.theme` – palette, typography, dark/light variants.
- `config/reporting.yaml::visual.cache_ttl` – caching window for charts reused across reports.
- `config/reporting.yaml::visual.dimensions` – default widths/heights per medium (PDF, dashboard, thumbnail).

#### Monitoring & Alerts
- Metrics: `visual.render_ms`, `visual.cache_hits`, `visual.render_errors`.
- Alert on sustained render failures or cache miss spikes (potential data issues).
- Dashboard: render latency distribution, top requested charts, cache effectiveness.

#### Module Interfaces
- Inputs: time-series from storage, analytics metrics, AI outputs.
- Outputs: chart files/HTML to PDF engine, web dashboard, social module.
- Cached assets stored in Redis/S3 for reuse.

### Market Analysis Narration
**Repository**: https://github.com/cjhutto/vaderSentiment (sentiment) + AI overseer outputs

#### Capabilities
- Synthesizes quantitative metrics, sentiment scores, and AI validator insights into narrative sections (executive summary, regime, risk, positions, outlook).
- Adjusts tone per audience (institutional vs retail) and highlights alerts that require operator review.

#### Data Flow
```
NarrativeRequest (section, tone) → gather metrics (regime, macro, performance, sentiment)
  → sentiment_engine.score(news)
  → AI composer (Claude/GPT) generate text using templates
  → optional human review
  → deliver narrative blocks to reporting/social modules
```

#### Configuration & Tuning
- `config/reporting.yaml::narratives.templates` – prompt + layout templates per section.
- `config/reporting.yaml::narratives.sentiment_sources` – news/signal feeds leveraged in VADER scoring.
- `config/reporting.yaml::narratives.tone_profiles` – wording presets per channel.
- `config/reporting.yaml::narratives.word_count` – min/max word targets per section.
- `config/reporting.yaml::narratives.review_required` – sections requiring human approval.

#### Monitoring & Alerts
- Metrics: `narrative.generate_ms`, `narrative.sentiment_score`, `narrative.review_flags`, `narrative.override_rate`.
- Alert when sentiment conflicts with quantitative reality (e.g., positive sentiment with negative performance) or when AI confidence is low.
- Dashboard: sentiment timeline, narrative approval queue, freshness per section.

#### Module Interfaces
- Inputs: regime classifier, macro overlay, performance/risk metrics, AI overseer decisions, news feeds.
- Outputs: narrative text to PDF engine, social broadcaster, operations dashboard; archived in `reports/narratives/{date}` with version control.
- Supports collaborative editing with change tracking for audit trail.

---

## 📱 Layer 9: Social Integration (Extensible)

### Discord Bot
**Repository**: https://github.com/Rapptz/discord.py

#### Capabilities
- Streams live trade/risk alerts, report links, and AI narratives into dedicated channels (ops, investors, premium subscribers).
- Supports slash commands for querying P&L, positions, run status, and toggling alert subscriptions.
- Enforces role-based access (internal vs premium vs public) and integrates with override workflows (approve/reject AI decisions).

#### Data Flow
```
AlertEvent (type, payload) → discord_formatter.render()
  → discord_client.send(channel_id, embed)
  → optional reactions/commands processed by bot → update system state (e.g., ack alert)
```

#### Configuration & Tuning
- `config/social.yaml::discord.bot_token` – bot authentication token.
- `config/social.yaml::discord.channels` – mapping of event types to channel IDs and roles.
- `config/social.yaml::discord.command_whitelist` – allowed commands per role.
- `config/social.yaml::discord.rate_limits` – throttle settings to avoid API bans.

#### Monitoring & Alerts
- Metrics: `social.discord.messages_sent`, `social.discord.command_count`, `social.discord.errors`.
- Alert on message send failures, unauthorized command attempts, or rate limit warnings.
- Dashboard: channel activity timeline, command usage, error heatmap.

#### Module Interfaces
- Inputs: events from execution, risk, AI overseer, reporting modules.
- Outputs: acknowledgements/command responses feeding back into systems (e.g., override approvals).
- Logs interactions in `social_logs/discord/{date}` for compliance.

### Telegram Bot
**Repository**: https://github.com/python-telegram-bot/python-telegram-bot

#### Capabilities
- Pushes trade notifications, PDF reports, macro alerts directly to mobile/desktop Telegram channels/groups.
- Implements subscriber verification and tiered alert levels; users can customize which alert types they receive.

#### Data Flow
```
AlertEvent → telegram_formatter.render()
  → telegram_client.send_message(chat_id, text/doc)
  → user command (/subscribe, /mute) → update subscription registry
```

#### Configuration & Tuning
- `config/social.yaml::telegram.bot_token`, `webhook_url` – bot credentials and webhook endpoint.
- `config/social.yaml::telegram.chats` – chat IDs and default alert sets.
- `config/social.yaml::telegram.subscription_flags` – available alert categories and defaults.

#### Monitoring & Alerts
- Metrics: `social.telegram.messages_sent`, `social.telegram.subscriptions`, `social.telegram.errors`.
- Alert on delivery failures or webhook downtime.
- Dashboard: subscriber growth, alert opt-in rates, error logs.

#### Module Interfaces
- Inputs: same event bus as Discord (converted to Telegram formatting).
- Outputs: subscription updates to Redis `social:subscriptions`, responses to broadcast manager for audit.
- Archives notifications for retention.

### Twitter Integration (Optional/Extensible)
**Repository**: https://github.com/tweepy/tweepy

#### Capabilities
- Posts market updates, performance snippets, and charts to public/premium Twitter accounts.
- Supports scheduled tweets and thread creation for longer-form insights.

#### Data Flow
```
SocialContent (text, media) → tweepy_client.create_tweet()
  → record tweet_id for tracking
```

#### Configuration & Tuning
- `config/social.yaml::twitter.api_keys` – OAuth credentials.
- `config/social.yaml::twitter.accounts` – mapping of content streams to handles.
- `config/social.yaml::twitter.schedule` – cron or event triggers for posting.

#### Monitoring & Alerts
- Metrics: `social.twitter.posts`, `social.twitter.engagement`, `social.twitter.errors`.
- Alert on auth failures or API quota exhaustion.

#### Module Interfaces
- Inputs: curated content from reporting/AI modules.
- Outputs: tweet metadata to analytics for engagement tracking.

### Reddit Integration (Optional/Extensible)
**Repository**: https://github.com/praw-dev/praw

#### Capabilities
- Automates daily discussion posts, due diligence summaries, and performance updates on Reddit communities.
- Handles flair/tag management and comment monitoring for compliance.

#### Data Flow
```
RedditContent → praw_client.subreddit(sub).submit(title, body)
  → monitor comments for keywords → escalate if needed
```

#### Configuration & Tuning
- `config/social.yaml::reddit.credentials` – client ID/secret, username/password.
- `config/social.yaml::reddit.subreddits` – list of communities and posting schedules.
- `config/social.yaml::reddit.flairs` – flair mapping per post type.

#### Monitoring & Alerts
- Metrics: `social.reddit.posts`, `social.reddit.comment_alerts`, `social.reddit.errors`.
- Alert on posting failures or flagged comments requiring moderator action.

#### Module Interfaces
- Inputs: curated content from reporting/AI modules.
- Outputs: comment alerts to ops team; engagement stats to analytics.

### Broadcast Manager

#### Capabilities
- Provides unified API for broadcasting events across all configured social channels with channel-specific formatting.
- Manages delivery fan-out, retries, and per-channel throttling.
- Tracks delivery outcomes and aggregates feedback (acknowledgements, failures).

#### Data Flow
```
Event (type, payload, audience) → broadcast_manager.route()
  for channel in active_channels:
      formatted = channel.format(event)
      channel.send(formatted)
      record outcome
```

#### Configuration & Tuning
- `config/social.yaml::broadcast.enabled_channels` – toggle per platform.
- `config/social.yaml::broadcast.retry_policy` – retries/backoff for failed posts.
- `config/social.yaml::broadcast.audience_map` – event type to channel routing rules.

#### Monitoring & Alerts
- Metrics: `social.broadcast.events`, `social.broadcast.success_rate`, `social.broadcast.retry_count`.
- Alert on sustained delivery failures or channel outages.
- Dashboard: broadcast queue health, per-channel success rates, retry heatmap.

#### Module Interfaces
- Inputs: events from reporting, AI overseer, execution/risk (converted to broadcast payloads).
- Outputs: per-channel delivery logs and aggregated analytics to monitoring stack.
- Stores delivery receipts in `social/broadcast_logs/{date}` for audit.

---

## 🔧 Additional Components

### How These Components Drive Trading Decisions

#### 1. Term Structure Analysis (Futures Basis)
**Repository**: https://github.com/lballabio/QuantLib-Python

##### Capabilities
- Computes futures-spot basis, contango/backwardation, and basis divergence across multiple tenors (front-month, quarter, year) to infer directional bias.
- Uses QuantLib curves to interpolate forwards and support multiple underlying assets (equity index, rates, commodities).

##### Data Flow
```
FuturesCurve + SpotPrice → term_structure_engine.compute_basis()
  → derive signals {direction, strength, confidence, tenor}
  → publish `analytics.term_structure` for signal integration
```

##### Configuration & Tuning
- `config/analytics.yaml::term_structure.thresholds` – contango/backwardation cutoffs.
- `config/analytics.yaml::term_structure.tenors` – list of futures expiries to monitor.
- `config/analytics.yaml::term_structure.lookback_days` – smoothing window for basis averages.

##### Monitoring & Alerts
- Metrics: `term_structure.basis_value`, `term_structure.signal_strength`, `term_structure.data_latency`.
- Alert when futures data stale or when basis shifts exceed configured bounds.

##### Module Interfaces
- Inputs: futures prices from AlphaVantage/IBKR, spot levels from ingestion layer.
- Outputs: directional bias to signal generator, narratives to AI overseer, risk manager adjustments.

#### 2. IV Surface & Smile Analysis
**Repository**: https://github.com/GBERESEARCH/volvisualizer

##### Capabilities
- Builds full implied volatility surface from option chain, measuring skew, smile, convexity, and vega/theta ratios by strike/expiry.
- Identifies optimal strikes (value opportunities), tail-risk warnings, and structural anomalies (inverted smiles).

##### Data Flow
```
OptionChain → surface_engine.fit_surface()
  → compute metrics (skew, smile steepness, convexity)
  → optimize strike selection for proposed trades
  → publish `analytics.iv_surface` with recommendations
```

##### Configuration & Tuning
- `config/analytics.yaml::iv_surface.interpolation` – method (sabr, spline, polynomial).
- `config/analytics.yaml::iv_surface.optimality_weights` – weights for convexity, relative IV, vega/theta.
- `config/analytics.yaml::iv_surface.alert_thresholds` – triggers for tail risk alerts.

##### Monitoring & Alerts
- Metrics: `iv_surface.fit_error`, `iv_surface.skew`, `iv_surface.smile_strength`.
- Alert when fit error high (insufficient data) or when unusual surface shape emerges.

##### Module Interfaces
- Inputs: normalized option quotes from AlphaVantage/IBKR.
- Outputs: strike/expiry recommendations to signal generator, risk manager, and AI narratives.

#### 3. Risk Reversal Analysis (0DTE → 90D)
**Repository**: Custom implementation

##### Capabilities
- Computes risk reversals (call vs put skew) across expiries (0DTE to 90D) to gauge sentiment and timing for momentum vs trend trades.
- Provides expiry selection guidance and momentum/trend classification.

##### Data Flow
```
IVSurface → risk_reversal_engine.compute_ladder()
  → evaluate skew differentials per expiry
  → classify sentiment + recommend expiry bucket
  → publish `analytics.risk_reversal` output
```

##### Configuration & Tuning
- `config/analytics.yaml::risk_reversal.expiries` – list of expiries to monitor.
- `config/analytics.yaml::risk_reversal.extreme_threshold` – absolute RR for momentum triggers.
- `config/analytics.yaml::risk_reversal.slope_threshold` – slope used to identify trend regimes.

##### Monitoring & Alerts
- Metrics: `risk_reversal.rr_value`, `risk_reversal.slope`, `risk_reversal.signal_confidence`.
- Alert when RR spikes beyond extremes or when data incomplete.

##### Module Interfaces
- Inputs: outputs from IV surface engine.
- Outputs: expiry recommendations to signal generator, context to risk manager/AI overseer.

#### 4. Cross-Asset Stress Index
**Repository**: Custom PCA implementation

##### Capabilities
- Aggregates cross-asset indicators (equities, credit, rates, FX, commodities) via PCA/weighted composite to score systemic stress (0-100).
- Feeds position sizing, strategy selection, and AI risk narratives.

##### Data Flow
```
CrossAssetData (vol, spreads, macro) → stress_engine.compute_index()
  → output stress score + components
  → publish `analytics.stress_index`
```

##### Configuration & Tuning
- `config/analytics.yaml::stress_index.factors` – data series included (VIX, HY spreads, rates, etc.).
- `config/analytics.yaml::stress_index.pca_window` – rolling window for PCA.
- `config/analytics.yaml::stress_index.thresholds` – normal/elevated/crisis cutoffs.

##### Monitoring & Alerts
- Metrics: `stress_index.value`, `stress_index.component_contribution`, `stress_index.data_staleness`.
- Alert when stress crosses thresholds or when data missing.

##### Module Interfaces
- Inputs: macro data (FinanceToolkit), market data (AlphaVantage/IBKR).
- Outputs: sizing adjustments to risk manager, context to AI overseer, overlays to reports.

### Integrated Signal Generation Logic

#### Data Flow
```
PrimarySignal (strategy alpha) → apply regime adjustment
  → microstructure & VPIN gating
  → macro overlay conflict check
  → term structure bias adjustment
  → IV surface strike optimization
  → risk reversal expiry confirmation
  → stress-index sizing
  → AI overseer validation
  → emit executable signal intent
```

#### Configuration & Tuning
- `config/signals.yaml::regime.strength_scalars` – scaling factors per regime state.
- `config/signals.yaml::liquidity.max_stress` – stress threshold to veto trades.
- `config/signals.yaml::vpin.threshold` – toxicity threshold for size reduction/skip.
- `config/signals.yaml::macro.conflict_threshold` – z-score cutoff for macro veto.
- `config/signals.yaml::stress.sizing_formula` – coefficients for stress-based sizing.
- `config/signals.yaml::ai.decision_threshold` – AI overseer approval requirement.

#### Monitoring & Alerts
- Metrics: `signals.generated`, `signals.vetoed`, `signals.ai_rejected`, `signals.size_adjustment_pct`, `signals.latency_ms`.
- Alert when veto rate spikes or AI rejection rate exceeds tolerance.
- Dashboard: funnel visualization (base signals → final approvals), per-stage drop-off stats, average confidence levels.

#### Implementation Sketch
```python
class SignalGenerator:
    async def generate_options_signal(self, symbol):
        base = await self.primary_strategy.compute(symbol)
        if not base:
            return None

        regime = self.regime_classifier.current_state()
        base.strength *= self.config.regime_scalars.get(regime, 1.0)

        if self.liquidity_monitor.stress(symbol) > self.config.max_liquidity_stress:
            return None

        if self.vpin_calculator.score(symbol) > self.config.vpin_threshold:
            base.size *= self.config.vpin_size_factor

        if self.macro_overlay.conflicts(base.direction, self.config.macro_conflict_threshold):
            return None

        base = self.term_structure.adjust(base)
        strike = self.iv_surface.optimize_strike(symbol, base)
        if not self.risk_reversal.confirms(symbol, base):
            return None

        stress = self.stress_index.value()
        final_size = base.size * (1 - stress / self.config.stress_divisor)

        signal = SignalIntent(
            symbol=symbol,
            action='BUY_CALL' if base.direction == 'bullish' else 'BUY_PUT',
            strike=strike,
            expiry=self.risk_reversal.select_expiry(base),
            size=max(final_size, 0),
            confidence=base.strength,
            stop_loss=self.risk_manager.calc_stop(base),
            take_profit=self.risk_manager.calc_targets(base)
        )

        if not await self.ai_overseer.validate(signal):
            return None

        return signal
```

---

## 🚀 System Integration

### Main Orchestrator (main.py)
```python
class QuantumTradingSystem:
    def __init__(self):
        # Load configuration
        self.symbols = config.load_symbols()  # Configurable list
        self.options_only = True  # No stocks, only options
        
        # Initialize all components
        self.data_ingestion = DataIngestionLayer()
        self.storage = RedisTimeSeriesStorage()
        self.analytics = AnalyticsEngine()
        self.signals = OptionsSignalGenerator()  # Options-specific
        self.execution = OptionsExecutionEngine()  # Long only
        self.ai_overseer = AIOverlord()
        self.reporter = ReportGenerator()
        self.social = SocialBroadcaster()
        self.dashboard = DashboardServer()
        
    async def run(self):
        # Millisecond event loop for options trading
        while True:
            for symbol in self.symbols:
                # Get options chains for 0DTE, 1DTE, 14+ DTE
                chains = await self.data_ingestion.get_options_chains(
                    symbol, 
                    expiries=['0DTE', '1DTE', '14-45DTE']
                )
                
                # Real-time Greeks from AlphaVantage premium
                greeks = await self.data_ingestion.get_live_greeks(chains)
                
                # Run analytics suite
                analytics = await self.analytics.analyze(symbol, chains)
                
                # Generate options-specific signals
                signal = await self.signals.generate(
                    symbol, chains, analytics
                )
                
                # AI validation before trade
                if signal and await self.ai_overseer.validate(signal):
                    # Execute long option position only
                    await self.execution.buy_option(signal)
                
                # Risk management for existing positions
                await self.manage_positions()
                
            # Update dashboard
            await self.dashboard.update_state()
            
            # Check for report generation (hourly/daily)
            if self.should_generate_report():
                report = await self.reporter.generate()
                await self.social.broadcast_report(report)
                
            await asyncio.sleep(0.001)  # 1ms loop
    
    async def manage_positions(self):
        """Manage existing option positions"""
        positions = await self.execution.get_positions()
        
        for position in positions:
            # Check trailing stops
            if self.should_trail_stop(position):
                await self.execution.update_stop(position)
            
            # Check take profit levels
            if self.hit_take_profit(position):
                await self.execution.partial_close(position)
            
            # Time-based exits for 0DTE/1DTE
            if self.should_time_exit(position):
                await self.execution.close_position(position)
            
            # Theta decay management for longer dated
            if self.excessive_theta_decay(position):
                await self.ai_overseer.alert_theta_risk(position)
```

---

## 📦 Installation & Setup

### requirements.txt
```
# Core
pandas==2.1.0
numpy==1.24.0
scipy==1.11.0

# Data Sources
alpha-vantage==2.3.1
ib-async==1.0.0

# Storage
redis==5.0.0
redistimeseries==1.4.5

# Analytics
py-vollib==1.0.1
hmmlearn==0.3.0
scikit-learn==1.3.0

# Backtesting
zipline-reloaded==3.0.0
pyfolio-reloaded==0.9.5
alphalens-reloaded==0.4.3

# AI
anthropic==0.7.0
openai==1.3.0

# Visualization
plotly==5.17.0
matplotlib==3.7.0

# Reports
fpdf2==2.7.5
Pillow==10.0.0

# Social
discord.py==2.3.2
python-telegram-bot==20.5

# Quant Libraries
QuantLib==1.31
mlfinlab==1.5.0
```

---

## 🎛️ Configuration Templates

### config/credentials.yaml
```yaml
alphavantage:
  api_key: "YOUR_PREMIUM_KEY"
  calls_per_minute: 600

ibkr:
  host: "127.0.0.1"
  port: 7497
  client_id: 1

redis:
  host: "localhost"
  port: 6379
  db: 0

anthropic:
  api_key: "YOUR_CLAUDE_KEY"

openai:
  api_key: "YOUR_OPENAI_KEY"

discord:
  bot_token: "YOUR_BOT_TOKEN"
  
telegram:
  bot_token: "YOUR_BOT_TOKEN"
```

### config/trading_params.yaml
```yaml
# Options-Only Trading Configuration
instruments:
  symbols: ["SPY", "QQQ", "AAPL", "TSLA", "NVDA"]  # Configurable list
  
  options:
    types: ["CALL", "PUT"]
    strategies: ["LONG_ONLY"]  # No naked selling
    
    expiries:
      - name: "0DTE"
        enabled: true
        max_position_pct: 10
        
      - name: "1DTE"
        enabled: true
        max_position_pct: 15
        
      - name: "14DTE+"
        enabled: true
        days_range: [14, 45]
        max_position_pct: 30

risk_management:
  trailing_stop:
    enabled: true
    type: "percentage"  # or "dollar"
    value: 20  # 20% trailing stop
    
  take_profit:
    enabled: true
    levels:
      - target: 25   # First target at 25%
        size_pct: 33  # Sell 1/3 position
      - target: 50   # Second target at 50%
        size_pct: 50  # Sell 1/2 remaining
      - target: 100  # Final target at 100%
        size_pct: 100 # Sell all remaining
        
  stop_loss:
    enabled: true
    percentage: 30  # -30% stop loss
    
  time_exits:
    0DTE:
      exit_before_close_minutes: 30
    1DTE:
      exit_before_close_minutes: 60
    default:
      hold_days_max: 21
```

---

## 📊 Layer 10: React Monitoring Dashboard

### Dashboard Architecture
**Repository**: Create new `quantum-dashboard/` directory

```
quantum-dashboard/
│
├── src/
│   ├── components/
│   │   ├── PositionsTable.tsx      # Live positions grid
│   │   ├── GreeksPanel.tsx         # Greeks aggregation
│   │   ├── PnLChart.tsx           # Real-time P&L
│   │   ├── RegimeIndicator.tsx     # Volatility regime status
│   │   ├── StressGauge.tsx        # Market stress 0-100
│   │   ├── VPINMonitor.tsx        # Order flow toxicity
│   │   ├── SignalFeed.tsx         # Live signal stream
│   │   ├── AlertsPanel.tsx        # AI alerts & warnings
│   │   └── MacroScorecard.tsx     # Economic indicators
│   │
│   ├── pages/
│   │   ├── Dashboard.tsx          # Main monitoring view
│   │   ├── Analytics.tsx          # Deep dive analytics
│   │   ├── Reports.tsx           # Generated reports
│   │   └── Config.tsx            # System configuration
│   │
│   ├── services/
│   │   ├── websocket.ts          # Real-time data stream
│   │   ├── api.ts               # REST API client
│   │   └── notifications.ts      # Browser notifications
│   │
│   └── App.tsx
│
├── package.json
└── README.md
```

### Tech Stack
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "typescript": "^5.0.0",
    "recharts": "^2.8.0",        // Charts
    "ag-grid-react": "^30.0.0",   // Data grids
    "socket.io-client": "^4.5.0", // WebSocket
    "react-query": "^3.39.0",     // Data fetching
    "tailwindcss": "^3.3.0",      // Styling
    "framer-motion": "^10.0.0"    // Animations
  }
}
```

### Dashboard Features
```typescript
interface DashboardState {
  // Real-time Monitoring
  positions: OptionPosition[]
  greeks: AggregatedGreeks
  pnl: { realized: number, unrealized: number }
  
  // Market State
  regime: 'calm' | 'elevated' | 'stressed'
  liquidity_stress: number  // 0-100
  vpin_score: number        // 0-1
  macro_score: number       // -3 to +3 std dev
  
  // Signals & Execution
  active_signals: Signal[]
  pending_orders: Order[]
  recent_fills: Execution[]
  
  // Risk Metrics
  var_95: number
  max_drawdown: number
  sharpe_ratio: number
  stress_index: number  // 0-100
  
  // System Health
  data_latency_ms: number
  api_calls_remaining: number
  system_alerts: Alert[]
}
```

### WebSocket Integration
```python
# Backend: FastAPI WebSocket endpoint
from fastapi import FastAPI, WebSocket
import asyncio

app = FastAPI()

@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await websocket.accept()
    while True:
        # Stream real-time updates
        data = {
            'positions': position_manager.get_current(),
            'greeks': greeks_engine.aggregate(),
            'regime': regime_classifier.current_state(),
            'signals': signal_generator.get_active(),
            'stress': cross_asset_stress.current(),
            'timestamp': time.time_ns() // 1_000_000  # ms
        }
        await websocket.send_json(data)
        await asyncio.sleep(0.1)  # 100ms updates
```

### Dashboard Layout
```
┌─────────────────────────────────────────────────────┐
│  Quantum Trading System  |  ⚡ Live  |  💚 All Systems │
├─────────────┬───────────────┬───────────────────────┤
│ P&L Today   │ Regime        │ Stress Index          │
│ +$12,450    │ ELEVATED 🟡   │ ▓▓▓▓▓░░░░░ 52/100   │
├─────────────┴───────────────┴───────────────────────┤
│                 POSITIONS (5 Active)                │
│ Symbol | Type | Strike | DTE | Delta | P&L | Status │
│ SPY    | CALL | 450   | 0   | 0.65  | +12% | ✅    │
│ QQQ    | PUT  | 380   | 1   | -0.45 | -5%  | 🔻    │
├──────────────────────────────────────────────────────┤
│         AGGREGATED GREEKS          │    SIGNALS     │
│ Delta: +2.45  Vega: 155           │ SPY: BUY CALL  │
│ Gamma: 0.89   Theta: -320         │ QQQ: WAIT      │
│ Charm: 12.5   Vanna: 45           │ TSLA: BUY PUT  │
├──────────────────────────────────────────────────────┤
│              MARKET MICROSTRUCTURE                   │
│ VPIN: 0.45 🟢 | Liquidity: NORMAL | MOC: -$2.5M     │
├──────────────────────────────────────────────────────┤
│                   AI ALERTS                          │
│ ⚠️ Unusual option flow detected in NVDA             │
│ ℹ️ Regime shift probability: 65% in next 2 hours    │
│ 🎯 Take profit triggered on SPY 450C                │
└──────────────────────────────────────────────────────┘
```

---

## 🏃 Quick Start Commands

```bash
# 1. Clone and setup
git clone [your-repo]
cd quantum-trading-system
pip install -r requirements.txt

# 2. Start Redis
docker-compose up -d redis

# 3. Configure credentials
cp config/credentials.yaml.example config/credentials.yaml
# Edit with your keys

# 4. Run system
python main.py

# 5. Monitor
tail -f logs/quantum-trading.log
```

---

## 📈 Performance Optimization for MacBook Pro

```python
# Leverage Apple Silicon
# config/system_config.yaml
optimization:
  multiprocessing: true
  process_count: 8  # Adjust based on M-series chip
  use_metal: true   # GPU acceleration for ML
  cache_size_gb: 16  # RAM cache
  redis_persistence: "appendonly"
```

---

## 🔄 Development Workflow

1. **Local Development** → Test on MacBook with local Redis
2. **Paper Trading** → IBKR paper account validation
3. **Limited Live** → Small position sizes
4. **Full Production** → Google Cloud deployment

---

## 📚 Documentation Links

- [AlphaVantage API Docs](https://www.alphavantage.co/documentation/)
- [IBKR API Guide](https://interactivebrokers.github.io/tws-api/)
- [Redis TimeSeries Commands](https://redis.io/docs/data-types/timeseries/)
- [Zipline Tutorial](https://zipline.ml/)
- [Claude API Reference](https://docs.anthropic.com/claude/reference/)
