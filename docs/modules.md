# Module Runbooks

Guides for implementing and operating each core module. Sections graduate from high-level specs to
step-by-step instructions as they are fleshed out.

### Environment & Namespace Conventions
- Redis keys are prefixed per environment: `dev:<key>`, `staging:<key>`, `prod:<key>` enforced via
  orchestrator bootstrap. Shared examples omit prefix for brevity.
- Schema versions are encoded in terminal segments when backward-incompatible changes occur (e.g.,
  `derived:analytics:{symbol}:v1`). Version bumps require update to consumers and documentation.
- `.env` must define `APP_ENV` (`dev`/`staging`/`prod`) and secrets; no PII is stored in Redis or
  logged. Social/watchdog payloads redact account identifiers before publishing.

## Analytics Engine

### Mission & Scope
- Transform vendor payloads from Redis (`raw:*`) into normalized analytics bundles under
  `derived:*`.
- Power downstream signal generation, risk management, dashboards, and watchdog review.
- Execute deterministically inside the orchestrator; no analytics job should depend on
  non-deterministic external calls once inputs land in Redis.

### Inputs & Freshness Contracts
| Required data | Redis key pattern | TTL (seconds) | Loader helper | Staleness action | Rationale (TTL ≥ cadence ×2) |
|---------------|------------------|---------------|---------------|------------------|-----------------------------|
| Alpha Vantage realtime options | `raw:alpha_vantage:realtime_options:{symbol}` | 60 | `load_alpha_vantage_option_chains` | Mark metrics `stale` if older than 45s. | 10s fetch cadence → 60s TTL gives 6 retries. |
| IBKR intraday bars (primary) | `raw:ibkr:bars:{symbol}:1min` | 900 | `load_ibkr_bars` (planned) | Require latest bar ≤90s old; stores rolling window (≥600 bars). | 30s refresh with keepUpToDate; 900s retains 15 min history for analytics windows. |
| Alpha Vantage intraday bars (fallback) | `raw:alpha_vantage:time_series_intraday:{symbol}` | 180 | `load_alpha_vantage_intraday_series` (planned) | Use only if IBKR feed unavailable; same freshness expectations. | 30s fallback cadence → 180s TTL ensures 6 cycles. |
| Alpha Vantage technicals (VWAP/MACD/BBANDS) | `raw:alpha_vantage:{indicator}:{symbol}` | 300 | `load_alpha_vantage_indicator` (planned) | Skip metric and log warning if missing. | 60s cadence → 300s TTL preserves 5 updates. |
| Alpha Vantage macro series | `raw:alpha_vantage:macro:*` | 86400 | `load_macro_series` | Use previous good value if current absent. | 6h cadence → 24h TTL covers daily retries. |
| Alpha Vantage news sentiment (equities only) | `raw:alpha_vantage:news_sentiment:{symbol}` | 1800 | `load_news_sentiment` (planned) | Mark narrative metrics `stale`. | 10m cadence → 30m TTL ensures multiple consumers. |
| IBKR quotes | `raw:ibkr:quotes:{symbol}` | 6 | `load_ibkr_quotes` | Require update ≤9s old for high-frequency metrics. | ~2s update expectation → 6s TTL covers 3 intervals. |
| IBKR level-2 depth | `raw:ibkr:l2:{symbol}` | 10 | `load_ibkr_level2_books` | Scheduler enforces rotation (3 concurrent subscriptions). Exchange must be specified per symbol (no SMART). Downgrade liquidity metrics if stale. | 5s rotation window → 10s TTL ensures one fresh snapshot. |
| IBKR ticks (trade prints) | `raw:ibkr:ticks:{symbol}` | 60 | `load_ibkr_ticks` (planned) | Needed for VPIN and short-horizon realized vol. | High-frequency stream trimmed to 60s to cover VPIN buckets. |
| IBKR account positions | `raw:ibkr:account:positions` | 30 | `load_ibkr_positions` | Without fresh positions, halt dealer exposure calc. | 15s polling → 30s TTL doubles buffer. |
| IBKR executions stream | `stream:ibkr:executions` | append-only | `load_recent_executions` (planned) | Needed for realized volatility/VPIN. | Stream persists events; consumers track IDs for idempotency. |

### Configuration Files
- `config/analytics.yml`: scheduler-driven manifest of analytics jobs. Top-level `defaults`
  provide shared `cadence_seconds` and `enabled` flags; each entry in `jobs` must define `name`,
  `type`, `cadence_seconds`, `symbols`, and `metrics`. Example:
  ```yaml
  defaults:
    cadence_seconds: 10
    enabled: true
  jobs:
    - name: refresh_high_frequency
      type: analytics.refresh.high_frequency
      cadence_seconds: 10
      symbols: ["SPY", "QQQ", "IWM"]
      metrics: ["dealer_greeks", "liquidity_snapshot"]
    - name: refresh_macro_daily
      type: analytics.refresh.macro_daily
      enabled: false
      cadence_seconds: 3600
      symbols: ["MACRO"]
      metrics: ["macro_overview"]
  ```
- `config/macros.yml`: enumerates macro series and mapping to symbol groups.
- `config/weights.yml` (planned): risk summary weighting per metric/asset class.
- Override paths by setting `ANALYTICS_CONFIG_PATH` in the environment; the scheduler reads that
  value during bootstrap so staging experiments do not disturb the default manifest.

Scheduler runtime emits job payloads into the Redis list `queue:analytics` (JSON objects with `job`
metadata, `queued_at`, and `retry_count`). Future analytics workers should consume from that queue,
acknowledge items explicitly, and persist completion status back to Redis/postgres per the
governance spec.

When `APP_ENV` is set, the orchestrator will prefix queue and key names (e.g.,
`dev:queue:analytics`) to isolate environments; workers must respect that convention when
subscribing and writing outputs.

### Runtime Flow
1. Scheduler dispatches `analytics.refresh.high_frequency` every 10 seconds for symbols requiring
   realtime updates (SPY/QQQ/IWM + active Techascope equities).
2. Job payload contains `symbol`, `metrics` list, and optional overrides (e.g., recompute only
   `dealer_greeks`).
3. Analytics worker pulls the payload, loads inputs via shared loaders, and validates freshness.
4. Metrics execute sequentially (ordered for dependency reuse) and publish outputs.
5. Final bundle written to `derived:analytics:{symbol}` with TTL 20s and appended to
   `stream:analytics`.
6. Quality status (`ok`, `stale`, `error`) stored alongside metadata for watchdog/dashboard.

### Scheduler Jobs & Ownership
| Job name | Owner | Cadence | Error budget (misses before alert) |
|----------|-------|---------|------------------------------------|
| `analytics.refresh.high_frequency` | Scheduler | 10s | 3 consecutive misses → `analytics_refresh_gap` warning. |
| `analytics.refresh.hourly` | Scheduler | 60m | 1 miss → warning; 2 misses → page. |
| `analytics.refresh.macro` | Scheduler | 6h | 1 miss within 24h → warning. |
| `analytics.snapshot.persist` | Orchestrator shutdown hook | On stop | Failure → page (ensures state saved). |

### Metric Implementation Guide

#### Dealer Greeks & Exposure (Priority Zero)
- **Inputs:** option chain greeks from Alpha Vantage, IBKR positions, IBKR quotes (for mark-to-market).
- **Calculations:**
  - Net delta = Σ(position_qty × option_delta × contract_multiplier).
  - Net gamma = Σ(position_qty × option_gamma × contract_multiplier × underlying_price).
  - Net theta/vega/rho taken directly from provided greeks × position.
  - Charm, vanna, volga recomputed via `analytics.math.black_scholes.greeks()` using mark price,
    implied vol, time to expiry, and interest rate (macro overlay).
  - Dealer assumption: treat positive quantity as dealer short exposure; aggregate by symbol.
- **Example:** 10 short SPY call contracts (100 multiplier) with delta 0.45 → net delta
  `10 * -1 * 100 * 0.45 = -450`. IBKR position long 500 shares adds +500; analytic net delta = +50.
- **Output:** `derived:dealer_exposure:{symbol}` JSON with fields `delta`, `gamma`, `theta`, `vega`,
  `rho`, `charm`, `vanna`, `volga`, `timestamp`, `data_sources`. TTL 20s.
- **Quality checks:** ensure implied vol not null; clamp extreme ratios; log if option chain missing.

#### Volatility Regime
- **Inputs:**
  - Realized volatility from IBKR 1-minute bars (default 30-minute lookback, configurable in
    `config/analytics.yml`). Retain ≥600 historical bars in Redis to allow longer windows when
    needed.
  - Implied vol (ATM) from option chain.
- **Calculations:**
  - Compute log returns `r_t = ln(price_t / price_{t-1})` from IBKR bars.
  - Realized σ = √(Σ(r_t²) × (252 × n_per_day / window_size)). For 30-minute window with 1-minute
    bars, `window_size = 30`.
  - Implied/realized ratio `iv_over_rv = implied_vol / max(realized_vol, ε)`.
  - Regime thresholds (configurable):
    - `calm` if `iv_over_rv < 1.1` and realized σ annualized < 20%.
    - `elevated` if `1.1 ≤ iv_over_rv < 1.5` or realized σ between 20–40%.
    - `stressed` otherwise.
- **Output:** `derived:vol_regime:{symbol}` TTL 120s including `realized_vol`, `implied_vol`, `ratio`,
  `regime`, `window_minutes`, `bar_source`.
- **Validation:** require ≥25 IBKR bars; if insufficient data or stale bars (>90s), mark metric
  `stale` and carry forward previous value.

#### Liquidity Stress Index
- **Inputs:** level-2 order book (top 10 levels), quotes, recent executions.
- **Calculations:**
  - Compute bid/ask depth = Σ size × price distance weighting (higher weight near touch).
  - Spread score = normalized bid-ask spread vs. 30-day median stored in config/postgres (todo).
  - Trade impact = executions volume in last 60s vs. depth.
  - Liquidity index scaled 0–100 using weighted components (weights default 0.5 depth, 0.3 spread,
    0.2 impact).
- **Output:** `derived:liquidity:{symbol}` TTL 20s with `index`, `depth_score`, `spread_bps`,
  `impact_score`, `status` (green/amber/red).
- **Checks:** ensure level-2 payload fresh (<7s). Scheduler must rotate subscriptions (max 3 live) and
  specify exchange per symbol (no SMART). If L2 data missing, fall back to quotes-only mode with
  degraded flag and note last rotation timestamp.

#### VPIN / Order Flow Toxicity (Phase 2)
- **Inputs:**
  - IBKR tick stream (`raw:ibkr:ticks:{symbol}`) providing trade prints with size, price, side if
    available.
  - IBKR executions stream for confirmed fills (fallback when tick side unknown).
  - Optional Alpha Vantage volume for gap filling.
- **Pre-processing:**
  1. Construct volume buckets of fixed notional/contract size (default 50k USD or 10 contracts) using
     volume-synchronized sampling. Each bucket aggregates consecutive trades until threshold reached.
  2. Classify trade direction via quote comparison (tick rule) or IBKR-provided aggressor flag.
- **Calculations:**
  - For each bucket `i`, compute buy volume `B_i` and sell volume `S_i`.
  - Volume imbalance `VI_i = |B_i - S_i| / (B_i + S_i)`.
  - VPIN over rolling window `n` buckets (default 50): `VPIN_t = (1/n) × Σ_{i=t-n+1}^{t} VI_i`.
  - Order flow toxicity score scaled 0–1; values >0.6 indicate elevated toxicity.
  - Record supporting stats: bucket duration, average bucket volume, last imbalance direction.
- **Output:** `derived:vpin:{symbol}` TTL 120s with fields `vpin`, `toxicity_score`,
  `bucket_size`, `window_buckets`, `last_bucket` (timestamp, imbalance sign).
- **Validation:** ensure at least `n` buckets available in the last 30 minutes; otherwise mark metric
  `stale`. Log bucket construction anomalies (e.g., prolonged gaps due to market halt).
- **Status:** implementation blocked until tick ingestion finalized; keep section updated once
  `load_ibkr_ticks` helper exists.

#### Macro Overlay Scores
- **Inputs:**
  - Macro series cached under `raw:alpha_vantage:macro:*` (GDP, CPI, inflation, treasury yields,
    federal funds rate).
  - Equity/futures reference prices (spot vs. futures basis from IBKR bars where applicable).
  - Configuration weights per symbol group in `config/macros.yml`.
- **Pre-processing:**
  - Build rolling window (default 8 quarters/24 months depending on series) from macro data stored in
    Redis. Retain historical values in analytics workspace to avoid repeated fetches.
  - Align release dates to market calendar; flag delayed data.
- **Calculations:**
  - Compute z-score for each macro indicator: `z = (latest_value - mean(window)) / std(window)`.
  - Map z-scores to qualitative states (e.g., GDP `z < -1` ⇒ `growth_contraction`).
  - Derive composite macro score per symbol or group using weighted sum of normalized indicators:
    `macro_score = Σ(weight_i × z_i)`.
  - Optionally compute yield curve slope (10Y - 2Y) and rate momentum using treasury yields.
  - Attach narrative flags (e.g., `inflation_pressured`, `rates_easing`) based on thresholds defined in
    config.
- **Output:**
  - `derived:macro_overlay:{group}` TTL 24h with `indicators` (raw values, z-scores, state) and
    `composite_score`.
  - Embed summary snippet into per-symbol analytics bundle when relevant (e.g., tech equities tied to
    growth outlook).
- **Validation:** raise warning if any macro series missing latest release or if standard deviation is
  zero (insufficient history). Allow fallback to previous overlay when new data unavailable.

#### Risk Summary & Dealer Edge Attribution
- **Inputs:** all prior metrics, realized PnL from IBKR PnL feed, option greeks.
- **Calculations:**
  - Risk score = weighted sum of normalized inputs (exposures, liquidity, volatility, macro).
  - Dealer edge = ΔPnL decomposition: e.g.,
    - `delta_contrib = previous_delta * price_change`.
    - `gamma_contrib = 0.5 * previous_gamma * price_change²`.
    - `theta_contrib = previous_theta * dt` (dt in days).
    - `vega_contrib = previous_vega * iv_change`, etc.
  - Summation check: Σ components ≈ observed IBKR unrealized change within tolerance 5%.
- **Output:**
  - `derived:risk_summary:{symbol}` TTL 20s with `score`, `drivers`, `alerts`.
  - `derived:dealer_edge:{symbol}` TTL 20s with component table and reconciliation values.
- **Monitoring:** if reconciliation error >10%, raise `analytics_mismatch` alert via observability module.

#### Volume & Open Interest Anomaly Detection
- **Inputs:**
  - Latest option chain snapshot (`raw:alpha_vantage:realtime_options:{symbol}`) providing
    per-contract `volume` and `openInterest`.
  - Aggregated historical baselines stored in Redis `state:analytics:volume_oi_baseline:{symbol}`
    (hash with keys `avg_volume_1d`, `avg_volume_5d`, `avg_oi_5d`, etc.) refreshed daily.
  - Baseline source of truth: nightly job persists aggregated stats to Postgres table
    `analytics.volume_oi_history` (date, symbol, total_volume, total_open_interest); Redis hash is a
    hot cache with TTL 48h to minimize database access.
- **Calculations:**
  - Current totals: sum volume/OI across option chain or by relevant strikes (configurable filters).
  - Baseline comparisons: compute z-scores `z_volume = (current - avg_5d) / std_5d`, same for OI.
  - Detect anomalies when |z| exceeds thresholds (default 2.0 for warning, 3.0 for alert).
  - Produce context: percentage change vs. previous session, contracts contributing most to spike.
- **Output:** `derived:volume_oi_anomaly:{symbol}` TTL 15m with fields `total_volume`, `volume_z`,
  `total_oi`, `oi_z`, `top_contracts` (list of strike/expiry with contribution), `baseline_window`.
- **Validation:** ensure baselines exist; if not, fall back to heuristics (flag `baseline_missing`).
  Verify standard deviation > 0 before dividing. Record baseline timestamp in output for auditing.

#### Correlation Matrix
- **Inputs:**
  - IBKR 1-minute bars for configured symbol set (`raw:ibkr:bars:{symbol}:1min`), retained for ≥600
    bars.
  - Symbol groups defined in `config/analytics.yml` (e.g., `techascope`, `indices`).
- **Pre-processing:**
  - Build synchronized return series over lookback window (default 3 hours / 180 bars) by aligning on
    timestamps; drop intervals with missing data.
  - Optionally resample to 5-minute returns for stability (configurable).
- **Calculations:**
  - Compute Pearson correlation matrix R where `R_ij = cov(r_i, r_j) / (σ_i σ_j)`.
  - Expose derived metrics: mean absolute correlation, eigenvalues/eigenvectors, cluster labels.
- **Output:** `derived:correlation:{group}` TTL 900s containing matrix (flattened), summary stats,
  eigen decomposition, and metadata (`lookback_minutes`, `bar_source`). Archive snapshots to
  Postgres `analytics.correlation_matrices` for historical studies.
- **Validation:** require at least 120 overlapping observations; if condition number of R exceeds
  threshold (ill-conditioned), mark `quality="warning"` and regularize (shrink toward identity).

#### MOC Imbalance Monitor
- **Inputs:**
  - IBKR market data with generic tick `165` (`Auction values`) requested via
    `IB.reqMktData(contract, genericTickList='165', snapshot=False)` for NYSE/NASDAQ symbols.
  - Optional aggregated order book data from level-2 snapshots during final 30 minutes.
- **Ingestion Contract:** store auction updates under `raw:ibkr:auction_imbalance:{symbol}` with
  fields `auctionPrice`, `auctionVolume`, `auctionImbalance`, `auctionType`, `timestamp`, `exchange`.
  Scheduler enables subscriptions around 15:30 ET and rotates respecting L2 limits.
- **Calculations:**
  - Net imbalance = `auctionImbalance` signed volume; compute notional vs. latest mid price.
  - Confidence scoring: combine absolute imbalance, ratio to average closing volume (baseline from
    `analytics.volume_oi_history`), and whether imbalance direction aligns with intraday trend.
  - Generate projected MOC impact by estimating price move `Δp = imbalance_notional / depth_5min`.
- **Output:** `derived:moc_imbalance:{symbol}` TTL 30m with fields `imbalance_shares`,
  `imbalance_notional`, `side`, `confidence`, `projected_move`, `auction_price`, `data_sources`.
- **Validation:** ensure auction data refreshed within 60s during final 15 minutes of session; mark
  `stale` outside the window. Alert when imbalance exceeds configured thresholds.

#### Futures Linkage & Basis
- **Inputs:**
  - Futures quotes/bars from IBKR (`raw:ibkr:quotes:{future_symbol}`, `raw:ibkr:bars:{future_symbol}:1min`).
  - Corresponding spot instrument prices (IBKR bars for equities or ETFs).
  - Contract metadata (`contract.multiplier`, expiry, days to maturity) from `reference.symbols`.
- **Calculations:**
  - Spot-futures basis: `basis = futures_price - spot_price`.
  - Annualized carry: `carry = (futures_price / spot_price - 1) × (365 / days_to_expiry)`.
  - Sentiment overlay: compare to historical basis mean (stored in Redis `state:analytics:basis_baseline`)
    to classify `contango`, `backwardation`, `neutral`.
  - Generate warning when basis diverges beyond `±2σ` from baseline or carry contradicts macro regime.
- **Output:** `derived:futures_linkage:{pair_id}` TTL 30m with fields `basis`, `carry`, `state`,
  `spot_symbol`, `future_symbol`, `days_to_expiry`, `baseline_z`.
- **Validation:** ensure both spot and futures data within 90s; fallback to previous output if market
  closed. Baseline data maintained via nightly job leveraging Postgres `analytics.futures_basis_history`.

#### IV Surface Curvature & Smile Skew
- **Inputs:**
  - Option chain data per symbol with implied vol per contract (from Alpha Vantage realtime options).
  - Interest rate and dividend assumptions from macro overlay / reference config.
- **Reason for Surface Reconstruction:** individual contract IVs are provided but irregularly spaced
  across strikes and expiries. Analytics requires a smooth surface to derive second-order metrics
  (curvature, skew). We employ spline interpolation on normalized moneyness/tenor grid to evaluate
  continuous IV surface.
- **Calculations:**
  - Convert strikes to log-moneyness `k = ln(K / S)` and time to expiry `τ` (in years).
  - Fit smoothing spline or SABR-inspired surface `σ(k, τ)` minimizing error vs. observed IVs with
    regularization (configurable lambda).
  - Curvature metric: second derivative of IV w.r.t. strike at ATM `∂²σ/∂k²`.
  - Smile skew: first derivative of IV w.r.t. strike (`∂σ/∂k`) at chosen delta (e.g., 25Δ).
  - Surface quality score based on residual RMSE.
- **Output:** `derived:iv_surface:{symbol}` TTL 20s containing sampled grid, `curvature`, `skew`,
  `residual_rmse`, and diagnostic flags. Persist reduced surface (key points) to
  `stream:analytics_surfaces` for history if needed.
- **Validation:** require minimum number of contracts per expiry (≥6). If fit error exceeds threshold,
  mark as `warning` and fall back to direct contract IV comparisons.

#### Risk Reversal Ladder
- **Inputs:**
  - Implied vols for calls/puts at prescribed deltas (e.g., 25Δ, 10Δ) derived from IV surface
    interpolation.
  - Expiry tenors of interest (0DTE, 1DTE, 7D, 30D, 90D) defined in `config/analytics.yml`.
- **Calculations:**
  - Risk reversal per tenor `RR_τ = IV_call_Δ - IV_put_Δ` (default Δ=25%).
  - Construct ladder array across tenors; compute slope metrics (term structure) and identify
    direction of skew.
  - Flag actionable states (`bullish_skew`, `bearish_skew`, `neutral`) with thresholds ±1σ derived from
    30-day history stored in Redis `state:analytics:rr_baseline:{symbol}`.
- **Output:** `derived:risk_reversal:{symbol}` TTL 20s with `rr_values` (per tenor), `term_slope`,
  `state`, and baseline stats. Append summary to analytics bundle for signal engine use.
- **Validation:** ensure IV surface fit succeeded for relevant tenors. If baseline missing, mark
  `state="unknown"` and log.

#### Cross-Asset Stress Index
- **Inputs:**
  - Equity indices (SPY, QQQ, IWM) volatility metrics from analytics outputs.
  - Rates/fixed-income proxies (e.g., treasury yield changes, futures basis) from macro/futures
    modules.
  - Volatility instruments (e.g., VIX or IBKR VX futures) if available.
- **Calculations:**
  - Normalize each component (z-score vs. 60-day history stored in Postgres `analytics.stress_components`).
  - Perform weighted PCA (weights configured) to extract first principal component representing stress.
  - Scale to 0–100 index via percentile mapping with historical reference.
- **Output:** `derived:stress_index:global` TTL 30m with component contributions, PCA loadings,
  `index_value`, `percentile`, and suggested regime label (`calm`, `watch`, `elevated`, `crisis`).
- **Validation:** ensure sufficient history for PCA; if new component missing, recalc with reduced set
  and note in metadata.

#### Dealer Edge Attribution Enhancements
- **Inputs:** existing dealer exposure outputs, IBKR PnL stream, execution slippage metrics,
  option greeks history.
- **Enhancements:**
  - Gamma decay adjustment: incorporate change in gamma exposure due to theta/time decay between runs.
  - Charm/Vanna contributions: include terms `charm_contrib = charm_previous × Δt × price_change` and
    `vanna_contrib = vanna_previous × ΔS × Δσ`.
  - Execution slippage: compare expected entry/exit price (from analytics) vs. actual fills captured in
    `stream:ibkr:executions` to attribute residual PnL.
  - Funding cost: integrate macro risk-free rate (federal funds) for carry adjustments.
- **Output:** extend `derived:dealer_edge:{symbol}` to include `components` array with each contributor,
  `expected_pnl`, `realized_pnl`, `slippage`, `residual`, and `quality`. Persist reconciliation details
  to Redis stream `stream:dealer_edge` for auditing.
- **Validation:** require synchronized timestamps between exposures and PnL updates (tolerance 5s). If
  mismatch exceeds threshold, mark reconciliation as `warning` and trigger alert for manual review.

### Output Schema & Storage
- Per-symbol bundle `derived:analytics:{symbol}` (TTL 20s) containing:
  ```json
  {
    "symbol": "SPY",
    "generated_at": "2025-09-27T14:32:11Z",
    "metrics": {
      "dealer_exposure": {...},
      "volatility_regime": {...},
      "liquidity": {...},
      "risk_summary": {...}
    },
    "quality": {
      "overall": "ok",
      "dealer_exposure": "ok",
      "volatility_regime": "stale"
    },
    "sources": {
      "raw_option_chain": "raw:alpha_vantage:realtime_options:SPY",
      "raw_level2": "raw:ibkr:l2:SPY"
    }
  }
  ```
- Append snapshot to `stream:analytics` with fields `symbol`, `generated_at`, `quality`, `payload_sha`.
- Optional Postgres archival: `analytics.metric_snapshots` with columns (`symbol`, `generated_at`,
  `metrics_json`, `quality_json`). Only required once long-term analysis demanded.

### Quality Gates & Alerting
- Freshness guard: bail early if more than two critical sources stale; set `quality.overall = "stale"`.
- Statistic watchdog: compare computed greeks vs. Alpha Vantage provided values; if drift >5% for two
  consecutive runs, emit `analytics_greek_drift` alert.
- Numerical sanity:
  - Clamp exposure magnitudes to ±1e9 notional.
  - Reject negative liquidity index; replace with `null` and flag warning.
- Logging: use structured logger with correlation IDs from scheduler payload for traceability.

### SLOs & Alert Thresholds
| Alert key | Threshold | Severity / Paging policy |
|-----------|-----------|---------------------------|
| `analytics_refresh_gap` | Missed 3 consecutive `analytics.refresh.high_frequency` jobs | Warning (Slack). |
| `analytics_write_failure` | Derived bundle write fails after retries | Page immediately. |
| `analytics_source_stale` | Any critical source stale for >45s across 3 cycles | Warning. |
| `analytics_metric_warning` | Metric validation flagged warning state for >10 minutes | Informational only. |

### Operational Procedures
- **Manual run (single symbol):**
  ```bash
  source .venv/bin/activate
  python -m src.analytics.cli refresh --symbol SPY --metrics dealer_greeks volatility_regime
  ```
- **Backfill using recorded payloads:**
  ```bash
  python -m src.analytics.cli replay --symbol SPY --from 2025-09-27T13:00 --to 2025-09-27T14:00
  ```
- **Inspect latest output:**
  ```bash
  python -m src.tools.peek redis derived:analytics:SPY
  ```
  (These commands will be formalized in the CLI reference doc.)
- **Health check:** verify `system:heartbeat:analytics_engine` < 15s old and `quality.overall=ok`.

### Implementation Checklist
- [ ] Confirm `config/analytics.yml` contains all required sources with max-age settings.
- [ ] Build/verify loaders for any new inputs (e.g., news sentiment, macro).
- [ ] Implement metric module with deterministic unit tests using fixtures under
  `tests/analytics/fixtures/` (leverage samples from `docs/samples`).
- [ ] Register metric in runner order; ensure outputs merged into per-symbol bundle.
- [ ] Update `docs/data_sources.md` if new raw keys introduced.
- [ ] Capture validation notes in `docs/verification/analytics/<metric>_<date>.md` once live.

### Cadence/TTL Alignment Summary
- High-frequency metrics (dealer exposure, liquidity, volatility regime) rely on feeds with TTL ≥ 3×
  their refresh cadence:
  - `raw:ibkr:quotes:{symbol}` TTL 9s vs. analytics loop 10s (quotes refresh ≤3s and extend TTL on
    every update).
  - `raw:ibkr:l2:{symbol}` TTL 10s with 5s rotation windows ensures at least one fresh snapshot per
    evaluation; metrics degrade gracefully when rotation misses occur.
  - `raw:ibkr:bars:{symbol}:1min` TTL 900s allowing 15 minutes of history; analytics require 30–60
    minutes for realized vol and correlation—rolling window maintained in-process using retained
    bars.
- Alpha Vantage fallback series (intraday, technical indicators) have TTL ≥ 5× cadence, providing
  buffer if IBKR sources momentarily unavailable.
- Macro/fundamental feeds carry multi-hour or multi-day TTLs aligned with their update frequency;
  analytics overlay caches reuse previous values when new releases absent.
- Baseline caches (`state:analytics:*`) use TTL 48h+ while canonical history resides in Postgres,
  preventing accidental eviction before nightly refresh.
- Derived outputs (`derived:analytics:{symbol}` TTL 20s) refresh every 10s; downstream signal engine
  must consume within 2 cycles or rely on stale-quality flags.

### Failure Modes & Responses
| Failure | Detection | Automated action | Alert |
|---------|-----------|------------------|-------|
| Source key stale (`raw:alpha_vantage:realtime_options` >45s) | Loader raises `StaleDataError` | Skip metric, set quality `stale` | `analytics_source_stale` warning after 3 consecutive skips. |
| IBKR L2 rotation over capacity | Scheduler detects pacing error 100 | Slow rotation cadence, log degraded | `analytics_l2_rotation_degraded` warning. |
| Redis write failure for derived bundle | Retry helper exceeds attempts | Fall back to event log, raise exception to orchestrator | `analytics_write_failure` page immediately. |
| Metric validation fail (e.g., correlation ill-conditioned) | Validator flag | Mark metric `warning`, persist diagnostic | `analytics_metric_warning` info-level (no page). |
| State persist on shutdown fails | Orchestrator exit hook | Retry once then continue with degradation flag | `analytics_state_persist_failed` page. |

## Signal Engine

### Mission & System Context
- Convert analytics outputs into risk-aware trade intents that survive institutional scrutiny.
- Enforce risk policies using live account data before any signal reaches the watchdog or execution
  engine.
- Maintain continuity across modules: signals originate from analytics, pass to watchdog for
  compliance, flow into the execution engine, and once executed, trigger downstream social/reporting
  automations. The runbook documents every handshake point.

### Data Acquisition & Refresh Cycle
| Input | Retrieval | Redis key(s) | TTL | Usage | Rationale |
|-------|-----------|--------------|-----|-------|----------|
| Analytics bundle | Analytics engine | `derived:analytics:{symbol}` | 20s | Entry logic, noise filters, context. | 10s evaluation cadence → 20s TTL (2×). |
| Dealer edge attribution | Analytics engine | `derived:dealer_edge:{symbol}` | 20s | Expected edge + components for sizing. | Synchronized with analytics bundle cadence. |
| Liquidity index | Analytics engine | `derived:liquidity:{symbol}` | 20s | Noise filter, Achilles lookup. | Aligned with analytics refresh; expires after two cycles. |
| VPIN / toxicity | Analytics engine | `derived:vpin:{symbol}` | 120s | Confirms order-flow regime. | VPIN updates 60s → TTL 120s. |
| Macro overlay & stress index | Analytics engine | `derived:macro_overlay:{group}`, `derived:stress_index:global` | 24h/30m | Higher-level gating, overnight risk. | Macro daily, stress 30m; TTL matches 4× cadence. |
| IBKR account summary | IBKR ingestion | `raw:ibkr:account:summary` | 60s | Capital & buying power for sizing. | 15s polling → TTL 60s (4×). |
| IBKR account/position PnL | IBKR ingestion | `raw:ibkr:account:pnl`, `raw:ibkr:position:pnl:{symbol}` | 60s | Daily loss guardrail, Kelly bankroll adjustments. | Same as account summary. |
| Active positions | Execution engine | `signal:active:*`, `exec:order:*`, Postgres `trading.trades` | sliding | Prevent overexposure, dedupe direction. | Active keys persist until trade closed; execution updates extend TTL. |
| Strategy config | Postgres → Redis | `config:strategy:{name}` | 600s | Thresholds, cooldowns, sizing mode. | Manual edits infrequent; 10m cache → watchers refresh. |
| Risk limits | Config cache | `config:risk_limits` | 600s | Global caps (contracts, notional, drawdown). | 10m align with config reload cadence. |
| Historical performance | Postgres | `analytics.signal_stats` | n/a (queried) | Win rate, payoff ratio for Kelly. | Queried directly; no TTL. |
| Last signal metadata | Redis | `state:signal:last:{symbol}:{strategy}` | 1d | Cooldown enforcement, duplication prevention. | Ensures daily context for dedupe; daily reset matches strategy horizon. |

**Account refresh policy:** a scheduler job `signal.account_snapshot` runs every 15s to copy the
latest IBKR account summary/PnL into `state:signal:account_snapshot`. Kelly sizing reads from this
snapshot; if missing or stale >60s, the engine falls back to Achilles minimal sizing or skips the
signal.

### Decision Pipeline (Per Job)
1. **Pre-flight checks:**
   - Confirm trading halt not active (`system:state:trading_halt`).
   - Ensure strategy/time window valid (e.g., 0DTE within market hours).
   - Verify account snapshot fresh and within risk bounds (daily loss, max leverage).
2. **Load analytics context:** fetch required metrics; ensure `quality.overall == ok`. If any critical
   input stale, log `stale_input` and exit quietly (increments metric for monitoring).
3. **Noise filters:** apply multi-layer gating (details below) to avoid reacting to microstructure
   noise.
4. **Edge assessment:** compute expected edge using dealer edge attribution (expected PnL vs. risk).
5. **Conflict checks:** evaluate current exposure, cooldowns, and pending signals to avoid duplicate or
   opposing trades.
6. **Sizing:** run Kelly/Achilles models with live bankroll and limits. If risk caps binding reduce
   size or abort (with logged reason `risk_cap_hit`).
7. **Signal assembly:** build canonical payload with instrumentation (analytics references, gating
   evidence, risk). Compute deterministic TTL/cooldown expiry times.
8. **Persistence & notification:**
   - Write to `signal:pending` and `stream:signals`.
   - Update `state:signal:last` with preview state (`pending`, timestamp, direction, metrics).
   - Emit structured log and metrics counters.
9. **Watchdog/Execution loop:** wait for review outcome; post-process per result.

### Scheduler Jobs & Ownership
| Job name | Owner | Cadence | Error budget (misses before alert) |
|----------|-------|---------|------------------------------------|
| `signal.evaluate.0dte` | Scheduler | 10s (market hours) | 3 consecutive misses → `signal_generation_gap` warning. |
| `signal.evaluate.1dte` | Scheduler | 10s | Same as above. |
| `signal.evaluate.14dte` | Scheduler | 60m (10:00–15:00) | 1 miss → warning. |
| `signal.evaluate.moc` | Scheduler | 30s (15:30–15:55) | 1 miss in window → warning; 2 → page. |
| `signal.account_snapshot` | Scheduler | 15s | 2 misses → `signal_account_stale` warning. |
| `signal.pending.monitor` | Orchestrator | 60s | 2 misses → page (ensures stale pending signals cleared). |

### Idempotency & Replay Guarantees
- **Decision fingerprint:** every evaluation computes `decision_sha = sha256(symbol|strategy|direction|instrument|size|conditions|generated_at_floor)`. This key is stored in
  `state:signal:decision:{symbol}:{strategy}` with TTL 1h.
- **Pending writes:** before writing to `signal:pending`, engine checks stored `decision_sha`. If
  identical within TTL, evaluation is treated as idempotent and skipped (`duplicate_decision` log).
- **Stream events:** `stream:signals` entries include `decision_sha` and are published with explicit
  message IDs. Watchdog/execution consumers maintain last seen `decision_sha` to avoid reprocessing.
- **Replay tooling:** CLI replay mode (`python -m src.signal.cli evaluate --replay-from ...`) honours
  `decision_sha`; repeated replays do not re-emit identical decisions unless `--force` supplied.

### Noise & Market-Structure Filters
- **Multi-factor gating:** a signal only passes when *all* of the following hold:
  1. **Trend confidence** from analytics ≥ strategy threshold (e.g., 0.6). Trend derived from combined
     metrics (dealer delta change + price momentum + macro overlay).
  2. **Liquidity healthy:** `liquidity.index ≥ min_liquidity` and depth not degraded; else degrade or
     abort.
  3. **Volatility regime** within allowed set; 0DTE refuses `stressed` by default.
  4. **VPIN** beyond configured band to ensure order flow conviction.
  5. **Cross-check with stress index:** skip when systemic stress elevated unless override set.
- **Noise dampening:** maintain short-term SMA of analytics signals (`state:signal:sma`) to smooth
  noisy flips. Only fire when change surpasses hysteresis band (e.g., gamma flip persisted two cycles).
- **Macro gating:** for 14DTE, require macro overlay trending positive; for MOC require macro alignment
  with imbalance direction.

### Duplicate & Conflict Prevention
- **Cooldown timers:** per symbol/strategy cooldown stored in `state:signal:last`. Attempting to reissue
  same direction before expiry returns `cooldown_active` and logs skip reason.
- **Position exposure check:** query execution engine (Redis `signal:active`, Postgres `trading.open_positions`).
  - Prevent stacking same-leg trades if it would exceed `max_contracts_per_symbol` or `max_delta_per_symbol`.
  - Block opposite-direction signal that would flip net exposure unless config allows scaling out.
- **Pending signal guard:** if `signal:pending` or `signal:approved` exists for symbol/strategy, new
  signal suppressed unless flagged as `force_replace` (e.g., to adjust size).
- **Noise oscillation guard:** maintain last two decisions; if sequential signals would alternate (call
  then put) within `min_direction_interval`, require analytics confidence delta > threshold before
  allowing reversal.
- **Rate limiter:** `metrics:signals` used to ensure generation count per hour stays within plan; if
  exceeded, engine slows cadence or halts.

### Strategy Playbooks (Expanded)

#### 0DTE (SPY, QQQ, IWM)
- **Prerequisites:** market open, liquidity strong, stress index < watch, no outstanding halt.
- **Analytics mapping:**
  - `dealer_exposure.gamma` crossing zero triggers potential entry; require `dealer_exposure.delta`
    supporting direction.
  - `liquidity.index` informs Achilles table and gating.
  - `vpin` chooses between momentum vs. mean-reversion template.
  - `risk_summary.score` ensures global risk not elevated (>70 aborts).
- **Instrument selection:**
  - Use `StrategyTemplate` config mapping scenarios to option structures (e.g., `gamma_flip_long` →
    2-point call vertical).
- **Exit metadata:** embed `exit_rules` (time-based, target multiple, stop) for execution engine to
  follow knowing watchers/execution interplay.

#### 1DTE (SPY, QQQ, IWM)
- Leans on same analytics but integrates overnight risk metrics. Additional gating: `macro_overlay` must
  be neutral or better; `stress_index` below elevated.
- Maintains `overnight_buffer` in risk section to adjust sizing or require partial hedge (documented for
  execution).

#### 14DTE Techascope Equities
- Consumes IV surface curvature, risk reversal ladder, macro overlay, and correlation matrix to pick
  names offering convexity with diversification.
- Signals stored longer; attach `monitoring_plan` referencing analytics watch metrics (e.g., `recalc_every`)
  for orchestrator to track in execution module.

#### MOC Imbalance
- Requires auction imbalance feed plus futures linkage confirmation. If futures basis contradicts
  imbalance direction, either shrink size or skip per config.
- Stores `auction_reference` metadata for later social reporting.

### Risk Models & Account Integration
- **Account snapshot usage:** `state:signal:account_snapshot` contains `net_liquidation`, `available_funds`,
  `cushion`, `daily_realized_pnl`. Kelly bankroll defaults to `available_funds × strategy.bankroll_pct`.
- **Kelly parameters:**
  - Edge from dealer edge; if component missing, degrade to Achilles.
  - Win rate from `analytics.signal_stats` (rolling). If dataset sparse (<20 trades), enforce fallback.
  - Risk per contract from execution templates (max loss). If zero (undefined), abort.
- **Achilles:** config-driven matrix defined per strategy/regime/liquidity; uses account snapshot to
  ensure notional < `max_notional_pct × net_liquidation`.
- **Global risk gate:** before finalizing, compute projected aggregate exposures (delta, gamma) using
  analytics exposures + proposed signal; abort if exceeding configured limits.

### State & Storage Contracts
| Key | TTL | Description |
|-----|-----|-------------|
| `signal:pending:{symbol}:{strategy}:{signal_id}` | 30m (extend on heartbeat) | Payload awaiting approval. Includes `watchdog_status` field updated by reviewer. |
| `signal:approved:{signal_id}` | 2h | Approved, pending/under execution. Execution removes once filled/cancelled. |
| `signal:active:{signal_id}` | Trade duration | Execution updates with fills, PnL, trailing risk. Drives social notifications. |
| `signal:archive:{date}` | 7d | Rolling index for quick lookup. Detailed history in Postgres. |
| `state:signal:last:{symbol}:{strategy}` | 1d | Stores last action (direction, size, outcome, cooldown expiry). |
| `state:signal:account_snapshot` | 60s | Latest account metrics for sizing. Populated by dedicated job. |
| `metrics:signals` | 1d | Aggregated counts, used for dashboards/alerts. |
| `stream:signals` | stream | Event bus for watchdog/execution/social listeners. |

Postgres integration:
- `trading.signals`: immutable record containing payload, analytics references, sizing inputs.
- `trading.signal_events`: timeline of state transitions (`pending`, `approved`, `active`, `closed`,
  `rejected`).
- `analytics.signal_stats`: nightly job computes performance stats feeding Kelly inputs.

### Watchdog → Execution → Social Flow
1. **Pending:** engine writes to `signal:pending` + `stream:signals`.
2. **Watchdog review:** loads analytics, risk context, crafts narrative; stores result in
   `watchdog:review:{signal_id}` with `status` (`manual`, `approved`, `rejected`).
3. **Approval:** autopilot or operator toggles to approved → engine copies payload to
   `signal:approved`. Execution module subscribed to events.
4. **Execution:** on fill, execution module updates `signal:active` with order IDs, fill prices, and
   pushes events to `stream:executions`. When trade closes, execution archives signal (updates
   `signal:archive` and Postgres).
5. **Social trigger:** social hub listens for `signal:active` transitions with `closed` status; merges
   analytics + execution details to craft outbound posts.

### Guardrails & Halts (Expanded)
- **Daily loss halts:** when cumulative realized PnL ≤ `-max_daily_loss`, set `system:state:trading_halt`
  (automated job). Signal engine respects immediately.
- **Symbol-specific throttles:** if execution module reports slippage beyond tolerance, set
  `state:signal:halt:{symbol}` for configurable duration (no new signals).
- **Market condition flags:** analytics can set `derived:analytics:{symbol}.quality.overall = degraded`;
  engine interprets as `no new entries` even if strategy triggered.
- **Manual override:** CLI `python -m src.signal.cli halt --symbol SPY --strategy 0dte` writes override
  keys with TTL; documented in operations guide.

### Failure Modes & Responses
| Failure | Detection | Automated action | Alert |
|---------|-----------|------------------|-------|
| Account snapshot stale >60s | `state:signal:account_snapshot` TTL check | Switch to Achilles sizing or skip signal | `signal_account_stale` warning (non-paging). |
| Analytics bundle missing/quality≠ok | Input validation | Abort evaluation, increment skip metric | `signal_stale_inputs` warning after 3 consecutive skips. |
| Cooldown/duplicate breach | Cooldown check returns active | Skip and log with reason `cooldown_active` | No alert (tracked via `metrics:signals:cooldown_skip`). |
| Pending signal stuck >10m | Cron job inspects `signal:pending` timestamps | Auto-cancel pending, log, notify watchdog | `signal_pending_timeout` page (high). |
| Risk limit exceeded (daily loss / exposure) | Risk manager comparison vs. caps | Set trading halt key, abort signals | `signal_risk_cap_block` warning; if persists >3 cycles, escalate to page. |
| Redis write failure | Exception on write | Retry 3× with backoff; if still failing raise | `signal_write_failure` page immediately. |

### Observability & Alerts
- Heartbeat: `system:heartbeat:signal_engine` TTL 15s.
- Metrics: `metrics:signals` counts; `metrics:signals:cooldown_skip` increments when dedupe triggers.
- Alerts:
  - `signal_generation_gap` (expected frequency missed).
  - `signal_pending_timeout` (>10m pending).
  - `signal_risk_cap_block` when risk guard denies multiple consecutive signals.
  - `signal_conflict_detected` when opposing signals suppressed.
- Logging: structured logs include `signal_id`, `strategy`, gating decisions, risk numbers, account
  snapshot summary. All logs include reference IDs for analytics/execution cross-correlation.

Sample log entries:
```json
{
  "level": "info",
  "event": "signal_accepted",
  "signal_id": "20250924-SPY-0dte-001",
  "strategy": "0dte",
  "direction": "LONG",
  "decision_sha": "c01f...",
  "kelly_fraction": 0.12,
  "contracts": 5,
  "account_snapshot": {"net_liquidation": 150000, "available_funds": 95000},
  "analytics_ref": "derived:analytics:SPY",
  "conditions": {"gamma_flip": true, "vpin": 0.64, "liquidity": 82}
}
```

### SLOs & Alert Thresholds
| Alert key | Threshold | Severity / Paging policy |
|-----------|-----------|---------------------------|
| `signal_generation_gap` | No accepted signals for 30 minutes during trading window while eligible setups exist | Warning (Slack); page if >60 minutes. |
| `signal_pending_timeout` | Pending signal older than 10 minutes | Page (Ops on-call). |
| `signal_risk_cap_block` | ≥3 consecutive evaluations blocked by risk caps within 15 minutes | Warning; page if persists >30 minutes. |
| `signal_account_stale` | Account snapshot older than 60s detected for 3 successive evaluations | Warning only. |
| `signal_conflict_detected` | Opposing signal suppressed 5 times within 30 minutes | Warning. |
| `signal_write_failure` | Redis write failure not recovered after retry | Page immediately. |

```json
{
  "level": "debug",
  "event": "signal_skipped",
  "symbol": "QQQ",
  "strategy": "0dte",
  "reason": "cooldown_active",
  "cooldown_expires_at": "2025-09-24T14:20:00Z",
  "decision_sha": "c01f...",
  "account_snapshot_age": 12,
  "metrics": {"gamma": 0.03, "liquidity": 65, "stress_index": 55}
}
```

### Operational Procedures
- Evaluate manually: `python -m src.signal.cli evaluate --symbol SPY --strategy 0dte` (respects guards).
- Force refresh strategy config cache: `python -m src.signal.cli refresh-config --strategy 0dte`.
- Inspect pending signals: `python -m src.signal.cli list --status pending --symbol QQQ`.
- Apply manual halt/resume: CLI writes to `state:signal:halt` keys; remove once issue resolved.
- Verify health: `redis-cli ttl system:heartbeat:signal_engine`, inspect `metrics:signals`.

**CLI Namespace & Glossary**
- All signal commands use `python -m src.signal.cli <verb>`. Supported verbs: `evaluate`, `list`,
  `approve`, `reject`, `halt`, `resume`, `refresh-config`.
- Commands are idempotent where applicable (`evaluate` obeys decision_sha, `halt` rewrites same key).
- Future automation should reuse these verbs to avoid alias sprawl.

### Implementation Checklist
- [ ] Build account snapshot job and verify signal engine refuses stale bankroll data.
- [ ] Implement strategy modules with full gating logic, validated via unit tests using sample analytics + account fixtures.
- [ ] Assemble Kelly/Achilles sizing with dynamic caps, including fallback when data insufficient.
- [ ] Implement dedupe/conflict logic referencing active/pending signals and execution exposure.
- [ ] Integrate watchdog approval pathway and ensure social hub receives final state transitions via
  `stream:signals`.
- [ ] Persist full lifecycle to Postgres and confirm analytics backtests can reproduce historical signals.

## Execution & Risk

### Mission & Scope
- Convert approved signals into executable IBKR orders while enforcing risk constraints and maintaining
  complete trade lifecycle records.
- Owns order routing, stop/target management, position supervision, and real-time exposure tracking.
- Serves as bridge between signal intent and actual trade execution, providing feedback loops to
  signal engine, analytics, and social/reporting modules.

### Data & Configuration Inputs
| Input | Source | Key / Table | TTL / cadence | Usage |
|-------|--------|-------------|---------------|-------|
| Approved signals | Signal engine | `signal:approved:{signal_id}` | TTL 2h | Primary payload for order creation. |
| Active signal state | Signal engine | `signal:active:{signal_id}` | live | Updated by execution to reflect fills/status. |
| Account snapshot | Signal account job | `state:signal:account_snapshot` | 60s | Validate capital, margin, net liquidation. |
| Account summary & PnL | IBKR ingestion | `raw:ibkr:account:summary`, `raw:ibkr:account:pnl` | 60s | Risk guardrails (daily loss, capacity). |
| Positions & exposure | IBKR ingestion | `raw:ibkr:account:positions`, `raw:ibkr:position:pnl:{symbol}` | 60s | Prevent over-sizing, track risk. |
| Order configuration | Postgres → Redis | `config:execution` | 600s | Default order types, slippage limits, client IDs. |
| Risk limits | Config cache | `config:risk_limits` | 600s | Max contracts, notional, per-symbol caps. |
| Strategy execution templates | Postgres | `reference.execution_templates` | n/a | Mapping from strategy to contract leg definitions, stop/target defaults. |
| Market data for monitoring | Analytics / IBKR | `derived:analytics:{symbol}`, `raw:ibkr:quotes:{symbol}` | 20s/6s | Trail stop logic, slippage checks. |
- Feature gates (default false): `config/execution.stop_monitor.enabled`,
  `config/execution.position_supervisor.enabled`, `config/execution.tp.enabled`,
  `config/execution.scaling_in.enabled`, `config/execution.scaling_out.enabled`.

### Scheduler Jobs & Ownership
| Job | Owner | Cadence | Error budget |
|-----|-------|---------|--------------|
| `execution.signal_consumer` (Redis stream listener) | Orchestrator TaskGroup | continuous | Restart on failure; alert if downtime >30s. |
| `execution.stop_monitor` | Scheduler (feature-gated) | 5s | 3 misses → warning. |
| `execution.pnl_watch` | Scheduler | 15s | 2 misses → warning. |
| `execution.reconcile_ibkr` (open orders/fills) | Scheduler | 60s | 1 miss → warning; 2 → page. |
| `execution.persist_snapshot` | Orchestrator shutdown hook | On stop | Failure → page. |
| `execution.position_supervisor` (feature-gated) | Scheduler | 5s | 3 misses → `execution_position_supervisor_gap` warning. |

### Order Lifecycle
1. **Signal ingestion:** subscribe to `stream:signals` and `signal:approved`. For each approved payload,
   load full signal object (including analytics references) and confirm approval timestamp.
2. **Pre-trade risk checks:**
   - Validate account snapshot freshness, daily loss thresholds, symbol-specific halts.
   - Ensure proposed size within config (per-symbol contracts, aggregate delta, notional). Compare
     against live positions and pending orders.
   - Confirm Kelly/Achilles sizing matches signal (within tolerance). If mismatch, log
     `sizing_disagreement` and either adjust or reject per policy.
3. **Contract discovery:** use `ib_insync` contract helpers (e.g., `Option`, `Stock`) per template.
   - Qualify contracts via `IB.qualifyContractsAsync` to ensure conId, exchange, currency set.
   - Verify exchange permissions align with level-2 rotation requirements (explicit exchange, no SMART
     default for depth-sensitive orders).
4. **Order construction:** map signal instrument definition to IBKR order(s):
   - Determine order type (market/limit) from config; apply slippage guard (limit price =
     mid ± slippage_bp).
   - Assign dedicated client ID (e.g., 201 for execution) to avoid collisions with market data clients.
   - Set transmit flag, time-in-force (`DAY` or `MOC` for imbalance trades), and attach orderRef linking
     to `signal_id`.
5. **Submission & acknowledgement:** send via `IB.placeOrder`. Capture returned `orderId`/`permId` and
   store in `exec:order:{trade_id}` with TTL 2h (extended on updates). Initial state `submitted`.
6. **Event processing:** subscribe to IBKR callback events:
   - `orderStatus` updates (Submitted, Filled, PartiallyFilled, Cancelled, Inactive).
   - `execDetails` for fills (price, size, liquidity type).
   - `commissionReport` for fees.
   Update `exec:order:{trade_id}` and `signal:active:{signal_id}` accordingly, append to Postgres
   tables (`trading.execution_events`, `trading.fills`).
7. **Post-fill management:** if signal defines stops/targets, register with `execution.stop_monitor`
   to evaluate against live market data.
8. **Completion:** upon closure (target hit, stop, manual exit), update `signal:active` to `closed`,
   push record to `signal:archive`, and emit event on `stream:trades`. Downstream social/signal stats
   modules consume from this point.

### Risk Guardrails
- **Position validation:** check aggregated exposures per symbol (delta, gamma) using analytics + live
  positions. Deny orders that breach `config:risk_limits` thresholds.
- **Notional & contract caps:** ensure total notional per symbol/strategy within allowed range; enforce
  `max_contracts_per_symbol` and `max_open_signals`.
- **Daily loss halt:** monitor realized PnL via `raw:ibkr:account:pnl`; once limit exceeded, set
  `system:state:trading_halt` and cancel pending orders.
- **Slippage guard:** compare executed price vs. mid price; if slippage > config threshold, mark trade
  for review and optionally halt symbol temporarily (`state:signal:halt:{symbol}`).
- **Timeout management:** auto-cancel orders pending beyond `max_time_in_market` (configurable) and
  flatten positions approaching market close (e.g., 15:55 for 0DTE).
- **Stop hierarchy:** support price-based, percentage, ATR/volatility-adjusted stops. For trailing
  stops, only adjust in direction of trade profit; never loosen stops.
- `execution.stop_monitor` obeys feature gate `config/execution.stop_monitor.enabled` (default false)
  and operates only for strategies explicitly opted in.

### Position Management & Trade State
- `execution.position_supervisor` job refreshes `trade:state:{trade_id}` every 5 seconds (using latest
  IBKR fills, quote data, and analytics) with fields:
  ```json
  {
    "trade_id": "20250927-SPY-0dte-003",
    "symbol": "SPY",
    "strategy": "0dte",
    "side": "long_call",
    "qty_open": 5,
    "avg_entry_price": 1.2,
    "unrealized_pnl": 185.0,
    "pnl_pct": 31.5,
    "max_favorable_excursion": 0.58,
    "max_adverse_excursion": 0.22,
    "tp_state": "armed",
    "sl_state": "armed",
    "scale_state": {"in": "eligible", "out": "eligible"},
    "legs": [
      {"id": "conid-123", "right": "CALL", "strike": 445, "qty_open": 5, "wap": 1.20},
      {"id": "conid-456", "right": "CALL", "strike": 447, "qty_open": -5, "wap": -0.72}
    ],
    "last_update": "2025-09-27T14:11:02Z"
  }
  ```
- Supervisor skips evaluations when market data stale (quotes older than 9s) or bid/ask spread exceeds
  configured threshold.
- Supervisor obeys feature gate `config/execution.position_supervisor.enabled` (default false); when
  disabled, existing stop_monitor retains control and trade state remains minimal.
- Trade state is authoritative for dashboards, social hooks, and analytics derived stats (MFE/MAE).
- Trade state stores weighted-average price (WAP) and filled quantity per leg; TP/scaling computations
  rely on WAP × remaining qty rather than original entry assumptions.
- Supervisor limits workload per tick (configurable `max_trades_per_cycle`, default 10); additional
  trades processed in next cycle to avoid long loops/GC pauses.

### Order Templates & Mapping
- `reference.execution_templates` defines instrument construction per strategy:
  ```yaml
  0dte:
    gamma_flip_long:
      legs:
        - {type: option, symbol: SPY, expiry_offset: 0, strike_delta: +0, right: CALL, ratio: 1}
        - {type: option, symbol: SPY, expiry_offset: 0, strike_delta: +2, right: CALL, ratio: -1}
      order_type: limit
      slippage_bps: 5
      stop:
        type: percent
        value: 40
      take_profit:
        type: percent
        value: 70
  ```
- Execution engine resolves `expiry_offset`/`strike_delta` using analytics context (e.g., ATM strike).
- Instruments may include stock legs for hedging; ensure margin impact validated before submission.

### Take-Profit (TP) Rules
- Configured in `config/execution.yml` per strategy/trade. Modes:
  - **Percent gain:** multiple tiers `{trigger_pct, close_pct}`; each trigger submits reduce-only
    orders for the specified fraction.
  - **Risk multiple:** close size at multiples of initial risk (1R, 2R, …) using entry vs. stop.
  - **Break-even arm:** once `pnl_pct` ≥ `be_arm_pct`, raise stop to ≥ entry price.
- Resolved plan stored in `exec:tp_plan:{trade_id}` (cached for trade duration). Example config:
  ```yaml
  tp:
    default_mode: percent
    percent:
      tiers:
        - {trigger_pct: 30, close_pct: 33}
        - {trigger_pct: 60, close_pct: 33}
        - {trigger_pct: 90, close_pct: 34}
    risk_multiple:
      r_targets: [1.0, 2.0]
    break_even:
      be_arm_pct: 25
  ```
- When tier triggered, supervisor submits reduce-only child orders, updates `trade:state` (`tp_state`),
  emits `trade.tp_hit` to `stream:trades`, and records in Postgres `trading.execution_events`.
- TP logic feature-gated via `config/execution.tp.enabled` (default false); tests must cover enabling/disabling per strategy.
- Orders are marked reduce-only where supported; when unavailable the engine computes
  `close_qty = min(requested, qty_open)` at submit time and re-validates against current `qty_open`
  just before sending. If quantity shrank due to fills, either adjust to remaining qty or cancel with
  `reduce_only_unavailable` log.

### Scaling In / Out
- **Scaling in (optional):** only add to winners when `pnl_pct ≥ scale_in_min_pnl`, liquidity healthy,
  and spreads within threshold. Config snippet:
  ```yaml
  scaling_in:
    enabled: false
    scale_in_min_pnl: 20
    step_qty: 1
    max_scale_in_steps: 2
    cooldown_sec: 60
  ```
  Supervisor verifies cooldown via `exec:scale_cooldown:{trade_id}` and total position vs. risk limits
  before placing additional reduce-only-aware limit orders.
- **Scaling out:** driven by TP tiers or trail-based reductions; respects `min_remaining_qty` and
  cooldown. Config:
  ```yaml
  scaling_out:
    enabled: true
    min_remaining_qty: 1
    cooldown_sec: 30
  ```
  On trigger, supervisor places partial close order, updates trade state (`scale_state.out`), and emits
  `trade.scale_out` events.
- Feature gating: both scaling features controlled by config flags; default-off for solo-dev simplicity.
- Supervisor sets and checks cooldown token `exec:scale_cooldown:{trade_id}`; attempts during cooldown
  log `scaling_cooldown_active` and skip.
- Reduce-only safety mirrors TP behavior: scaling orders compute close quantity against live
  `qty_open`, rechecking immediately before submission; if available reduce-only flag rejected,
  log `reduce_only_fail` and either derive delta or abort per config.

### Social Publishing Hooks
- Execution emits structured events to `stream:trades` for social hub consumption:
  - `trade.opened` (first fill) with entry, risk, TP plan summary.
  - `trade.scale_in`, `trade.scale_out` with quantities, reasons, `pnl_pct`.
  - `trade.stop_trail_adjusted` capturing stop changes.
  - `trade.closed` with final PnL, hold time, MFE/MAE.
- Social hub batches scale events within 30s for rate-limited channels; `trade.closed` is never batched
  and publishes immediately. Every trade event includes `env` field (`dev`/`staging`/`prod`) so sandbox
  data never leaks to prod channels.
- All payloads exclude sensitive account info and honor env prefixing.

### Order Semantics & Reduce-Only Handling
- Use reduce-only flag where broker supports; otherwise compute delta quantity to prevent net flips.
- Partial exits prefer limit orders with slippage guard; supervisor escalates to market after timeout.
- Bracket orders: when parent with attached stop/limit exists, modify child orders rather than
  cancelling/recreating to reduce broker churn.
- For multi-leg spreads, TP/scaling actions operate on leg pairs maintaining original ratios unless
  `allow_legging` explicitly enabled in template.
- Zero-bid or illiquid options: if bid == 0 or spread exceeds `max_spread_bps`, supervisor pauses TP
  and trailing adjustments; risk module may escalate to market-on-gap exit when `risk_summary.alert`
  indicates elevated risk.
- Stop-limit mapping: default stop-limit offset (bps) defined per strategy (`config/execution.stop_limit_offset_bps`);
  after two consecutive "not triggered / no fill" cycles, fallback to market stop to ensure exit.
- Market close behavior governed by `config/execution.zero_dte_flatten_time_et` (e.g., 15:55) with
  `grace_sec` to allow cancels; supervisor cancels pending orders and flattens positions after deadline.

### State & Storage Contracts
| Key | TTL | Description |
|-----|-----|-------------|
| `exec:order:{trade_id}` | 2h (extends on updates) | Current order state, IBKR IDs, timestamps, stop/target info. |
| `exec:stop_monitor:{trade_id}` | 30s heartbeat | Tracking info for trailing stops (price refs, thresholds). |
| `signal:active:{signal_id}` | trade duration | Extended with execution status (fills, PnL, stop state). |
| `trade:state:{trade_id}` | trade duration | Live position snapshot (qty, avg price, MFE/MAE, TP/SL/scale states). |
| `exec:tp_plan:{trade_id}` | trade duration | Resolved TP tier configuration for the trade. |
| `exec:scale_cooldown:{trade_id}` | configurable | Cooldown marker preventing rapid re-scaling. |
| `stream:trades` | stream | Append-only log of execution lifecycle events (opened, scale, stop trail, closed). |
| `state:execution:halt:{symbol}` | configurable | Symbol-level halt (slippage, errors). |

Postgres tables:
- `trading.trades`: high-level record (signal metadata, instrument, entry/exit times, PnL).
- `trading.fills`: each fill with orderId, execId, liquidity, commission.
- `trading.execution_events`: status transitions, stop adjustments, manual overrides.
- `trading.stop_adjustments`: history of trailing stop moves with reason.

### Idempotency & Reconciliation
- `trade_id` generated as deterministic hash of `signal_id` (single trade per signal). Replays of
  `signal:approved` events check existing `exec:order:{trade_id}`; if present, skip order creation.
- `stream:trades` includes `event_id = sha256(trade_id|status|timestamp_floor)` for consumer idempotency.
- Reconciliation job `execution.reconcile_ibkr` periodically requests open orders/fills from IBKR and
  compares with internal state; discrepancies flagged and corrected (e.g., missing fill appended).
- On IBKR reconnect, reconciliation performs three-step recovery: (1) rebuild open orders/fills,
  (2) reseed `exec:stop_monitor:{trade_id}` and `trade:state:{trade_id}`, (3) restart
  `execution.position_supervisor` before resuming adjustments.

### Failure Modes & Responses
| Failure | Detection | Automated action | Alert |
|---------|-----------|------------------|-------|
| IBKR order reject (code 201+) | `orderStatus` callback | Mark signal as `rejected`, notify watchdog, halt symbol if repeated | `execution_order_reject` page if recurring. |
| Pacing violation (code 100) | IBKR error | Backoff & retry with increased delay; log degraded state | `execution_pacing_violation` warning. |
| Account snapshot stale | Snapshot TTL >60s | Suspend new orders, notify signal engine | `execution_account_stale` warning. |
| Stop monitor missed runs | Scheduler miss count >3 | Trigger rescan across active trades | `execution_stop_monitor_gap` warning. |
| Redis write failure | Write attempt fails after retries | Raise exception → orchestrator restart task | `execution_write_failure` page immediately. |
| IBKR disconnect | Connection listener detects drop | Enter recovery mode, request open orders upon reconnect | `execution_ibkr_disconnect` warning; page if down >2 min. |

### Observability & Alerts
- Heartbeat key `system:heartbeat:execution_engine` TTL 10s.
- Metrics published to `metrics:execution` (orders_submitted, fills, slippage_bps_avg, stop_hits).
- Alerts thresholds:
  - `execution_fill_latency_high`: average submit→fill > 120s → warning; >240s → page.
  - `execution_slippage_exceeded`: slippage > threshold for 3 trades in 15 min → warning; if persists,
    halt symbol and page.
  - `execution_pending_timeout`: order in `Submitted` > 5 minutes → warning, auto-cancel.
- Logs: structured JSON including `trade_id`, `signal_id`, `order_id`, `status`, `fills`, slippage stats.
- Additional metrics:
  - `execution.tp_hits_total{tier}`
  - `execution.scale_in_total`, `execution.scale_out_total`
  - `execution.mfe_mae_ratio`
  - `execution.social_publish_latency_ms`
- Additional alerts:
  - `execution_scale_thrash`: >3 scale events within <120s → warning.
  - `execution_tp_miss`: TP armed but unfilled within configured timeout → warning.
  - `execution_reduce_only_fail`: broker rejects reduce-only request → warning escalating to page on
    retry failure.

### Logging Examples
```json
{
  "level": "info",
  "event": "order_submitted",
  "trade_id": "20250924-SPY-0dte-001",
  "signal_id": "20250924-SPY-0dte-001",
  "order_id": 12345,
  "perm_id": 67890,
  "type": "LMT",
  "limit_price": 1.25,
  "contracts": 5,
  "exchange": "CBOE",
  "client_id": 201
}
```

```json
{
  "level": "warn",
  "event": "order_cancelled_due_to_slippage",
  "trade_id": "20250924-QQQ-0dte-002",
  "signal_id": "20250924-QQQ-0dte-002",
  "order_id": 54321,
  "reason": "slippage_exceeded",
  "allowed_slippage_bps": 5,
  "observed_slippage_bps": 9,
  "action": "symbol_halted"
}
```

```json
{
  "level": "info",
  "event": "trade.scale_out",
  "trade_id": "20250927-SPY-0dte-003",
  "symbol": "SPY",
  "strategy": "0dte",
  "qty_closed": 2,
  "remain_qty": 3,
  "tier": "tp_60",
  "pnl_pct": 62.4,
  "timestamp": "2025-09-27T14:20:03Z"
}
```

### Operational Procedures
- **Manual cancel:** `python -m src.execution.cli cancel --trade-id 20250924-SPY-0dte-001`.
- **Modify stop:** `python -m src.execution.cli adjust-stop --trade-id ... --percent 25` (writes to
  `exec:stop_monitor`).
- **Flatten symbol:** `python -m src.execution.cli flatten --symbol SPY` (cancels orders, closes
  positions).
- **Reconcile now:** `python -m src.execution.cli reconcile --symbol SPY` triggers immediate open-order
  sync.
- **Health check:** ensure `system:heartbeat:execution_engine` TTL < 10s; inspect `metrics:execution`.
- **Force scale out:** `python -m src.execution.cli scale-out --trade-id <id> --qty 1 --reason manual_tp`.
- **Toggle scaling:** `python -m src.execution.cli scaling --trade-id <id> --enable-in true --enable-out true`.
- **Preview TP plan:** `python -m src.execution.cli tp-plan --trade-id <id>`.

### Simulation & Test Hooks
- Supervisor and stop monitor can run against recorded market data using the simulated quote feed at
  `tests/fixtures/quotes/` (API: `python -m src.execution.sim supervisor --feed tests/fixtures/quotes/sp y_20250927.json`).
- Tests should stub IBKR responses and feed deterministic quote streams to validate TP/stop/scaling
  decisions without live IBKR access.

### Implementation Checklist
- [ ] Build stream consumer for `signal:approved` with idempotent processing.
- [ ] Implement contract discovery and order template resolver using `ib_insync` helpers.
- [ ] Integrate risk guardrails (notional, exposure, daily loss) with live account data.
- [ ] Implement stop/target monitoring loop referencing live quotes/analytics.
- [ ] Persist execution lifecycle to Redis/Postgres and ensure reconciliation job keeps state in sync.
- [ ] Provide comprehensive unit/integration tests using paper account fixtures.
- [ ] Implement TP tier calculator, scaling eligibility checks, reduce-only sizing (unit tests).
- [ ] Add async integration test: open trade → hit TP tier → scale-out event emitted, trade state updated,
      trade closed triggers `trade.closed` event.
- [ ] Validate social hook by injecting `trade.scale_out` event and confirming social hub enqueues message.
- [ ] Ensure `config/execution.tp` and `config/execution.scaling_*` feature gates default to false and
      can be toggled per strategy.
- [ ] Confirm `config/execution.position_supervisor.enabled` and `config/execution.stop_monitor.enabled`
      default to false and are honored per-strategy.
- [ ] Test reduce-only fallback paths, multi-leg coherence, zero-bid handling, and stop-limit fallback
      behaviors via simulated feeds.

## Scheduler & Orchestrator

### Mission & Scope
- Operate the unified job scheduler that drives ingestion, analytics, signals, execution monitors, and
  housekeeping tasks.
- Enforce rate limits and rotation policies via token buckets/queues while providing deterministic,
  replayable dispatch semantics.
- Persist job state so restarts resume cleanly; expose observability hooks for operators and CLI.

### Components & Configuration Inputs
| Component | Config source | Description |
|-----------|---------------|-------------|
| `scheduler.runner.Scheduler` | `config/runtime.yml` (`modules.scheduler.enabled`) | Main runner launched by orchestrator when enabled. |
| Job definitions | `config/schedule.yml` | Cron expressions, jitter, rotation groups, token bucket bindings, feature flags. |
| Token buckets | `config/schedule.yml` (`buckets:`) | Defines refill rate, capacity per API (e.g., Alpha Vantage 600 cpm). |
| Rotation groups | `config/schedule.yml` (`rotations:`) | Symbol queues for L2 depth, quotes, etc. |
| Observability | `config/observability.yml` | Heartbeat TTL, alert thresholds for scheduler gaps. |
| Feature gates | `config/runtime.yml` per module | Scheduler respects module-disabled flags, skipping job dispatch for disabled modules. |

### Scheduler Jobs & Ownership Summary
| Job ID pattern | Owner | Purpose | Default cadence | Token bucket | Error budget |
|----------------|-------|---------|-----------------|---------------|--------------|
| `analytics.refresh.*` | Scheduler | Trigger analytics metrics | 10s / 60m / 6h | `av_realtime`, `av_macro` | 3 consecutive misses → warning. |
| `signal.evaluate.*` | Scheduler | Evaluate strategies | 10s–60m | `ibkr_eval` | See signal runbook. |
| `execution.*` | Scheduler | Stops, PnL, supervisor | 5–60s | `ibkr_execution` | 3 misses → warning. |
| `ingestion.*` | Scheduler | Alpha Vantage / IBKR fetches | Per endpoint | `av_rest`, `ibkr_streams` | 3 misses → warning; >5 → page. |
| Housekeeping (`scheduler.persist_state`, `scheduler.metrics_flush`) | Scheduler | State persistence | 5s / 60s | n/a | 1 miss → warning. |
| Shutdown flush | Orchestrator | Persist state on exit | on stop | n/a | Any failure → page. |

### Runtime Flow
1. Scheduler loads `config/schedule.yml` at startup, building `ScheduledJob` instances with cron,
   jitter, rotation, and bucket associations.
2. Main loops:
   - `_dispatch_loop`: evaluates due jobs, checks token buckets, emits dispatch payloads to
     `stream:schedule:{job_id}` with `scheduled_for`, `dispatched_at`, `rotation` (if any), and
     `decision_sha` for idempotency.
   - `_heartbeat_loop`: updates `system:heartbeat:scheduler` and per-job `system:schedule:last_run`.
   - `_state_loop`: every 5s (configurable) persists JSON snapshots to `state:scheduler:jobs`,
     `state:scheduler:buckets`, `state:scheduler:rotations`.
3. Token buckets consume tokens on dispatch; if insufficient, scheduler logs `bucket_empty` and defers
   job until refill time. Buckets refill deterministically using event loop time.
4. Rotation queues cycle through configured symbols; current pointer stored in
   `state:scheduler:rotations` for resume.
5. Orchestrator monitors scheduler task; restart triggers state reload via `load_scheduler_state()`.
6. Cold-start catch-up is bounded: scheduler only dispatches up to `max_catchup_iterations` (configurable,
   default 3) per job to avoid flooding with hours of backlog; remaining work spreads over future cycles.

### State & Storage Keys
| Key | TTL | Description |
|-----|-----|-------------|
| `system:heartbeat:scheduler` | 15s | Scheduler heartbeat timestamp. |
| `system:schedule:last_run:{job}` | 60s | Last successful dispatch time per job. |
| `stream:schedule:{job}` | stream | Dispatch events consumed by module workers (idempotent IDs). |
| `state:scheduler:jobs` | persistent | JSON map job → next_run. |
| `state:scheduler:buckets` | persistent | JSON map bucket → token count, last_refill. |
| `state:scheduler:rotations` | persistent | JSON map job → rotation queue pointer/order. |
| `state:scheduler:lock` | optional TTL | Config reload lock (SETNX with TTL, default 30s). |

Schema versions appended with `:v1` when a breaking change occurs (e.g., `stream:schedule:{job}:v1`).

### Idempotency & Replay
- Each dispatch event includes `dispatch_id = sha256(job|scheduled_for|rotation|sequence)` ensuring
  idempotent consumption by downstream modules.
- Workers record last processed `dispatch_id`; replays (e.g., rebuilding from `stream:schedule`) skip
  duplicates.
- Replay dispatches include `event_type=replay` field in stream payloads so downstream consumers can
  differentiate (e.g., avoid re-posting to social). Normal dispatches use `event_type=scheduled`.
- `scheduler.snapshot()` exposes current job schedule, bucket levels, rotation state; CLI commands read
  this with optional persisted state fallback when scheduler offline.

### Failure Modes & Responses
| Failure | Detection | Automated action | Alert |
|---------|-----------|------------------|-------|
| Job dispatch lag (missed 3 cycles) | `system:schedule:last_run` staleness | Mark job `degraded`, log, attempt catch-up dispatch | `scheduler_job_lag` warning. |
| Token bucket misconfiguration (negative tokens) | Validation on load | Set bucket to safe defaults, log error | `scheduler_bucket_invalid` warning. |
| Redis stream write failure | `XADD` retry exhausted | Raise exception → orchestrator restarts scheduler | `scheduler_dispatch_write_failure` page. |
| State persistence failure | `_state_loop` exception | Retry once; if still failing, log and continue | `scheduler_state_persist_failed` warning; page if two consecutive failures. |
| Cron parsing error on reload | Config reload | Job disabled, log critical | `scheduler_config_error` page. |
| Orchestrator shutdown without flush | Shutdown hook | Force `persist_scheduler_state()`; on failure log | `scheduler_shutdown_persist_failed` page. |

### Observability & Alerts
- Metrics namespace `metrics:scheduler` (jobs_dispatched_total, bucket_consumed, bucket_starved, rotation_advances).
- Additional metric `metrics:scheduler.jobs_skipped_disabled` tracks jobs skipped because dependent
  modules disabled (feature gates).
- Alerts & thresholds:
  - `scheduler_gap`: job lag > 2× cadence → warning, >4× → page.
  - `scheduler_bucket_starved`: bucket empty for >5 consecutive attempts → warning.
  - `scheduler_rotation_stuck`: rotation pointer unchanged for >N cycles (default 10) → warning.
  - `scheduler_rotation_over_capacity`: rotation queue length exceeds allowed concurrency (e.g., L2 >3)
    → warning, log degraded state `rotation_over_capacity`.
- Logging includes `job_id`, `scheduled_for`, `dispatch_id`, bucket status, rotation pointer.

### CLI & Operations
- Start/stop: `python -m src.main --module scheduler` (respects `APP_ENV`).
- Inspect snapshot: `python -m src.scheduler.cli snapshot` prints next runs, buckets, rotations.
- View job stream: `python -m src.scheduler.cli tail --job analytics.refresh.high_frequency`.
- Trigger manual dispatch: `python -m src.scheduler.cli dispatch --job signal.evaluate.0dte --rotation SPY`
  (respects token buckets and risk gates, so manual actions never exceed vendor limits).
- Pause job: write `state:scheduler:pause:{job}` with TTL or use CLI `pause` command (feature gate
  default off).

### Operational Procedures
- **Health check:** `redis-cli ttl system:heartbeat:scheduler` should return positive value; check
  `metrics:scheduler` for bucket starve counters.
- **Config reload:** update `config/schedule.yml`, run `python -m src.scheduler.cli reload`; CLI acquires
  `state:scheduler:lock` (SETNX with 30s TTL), waits for current dispatch loop to complete, reloads
  configuration, then flushes state.
- **Emergency stop:** orchestrator CLI `python -m src.main --stop scheduler` gracefully stops scheduler,
  persisting state.
- **Replay assist:** to replay missed jobs, use `python -m src.scheduler.cli replay --job signal.evaluate.0dte --since 2025-09-27T14:00:00Z` which re-emits events with new dispatch IDs while tagging as replay for consumers.

### Configuration Guidelines
- Ensure each job declares `module_dependency`; dispatcher auto-skips when dependency disabled to
  avoid flooding (e.g., disable analytics jobs if analytics module off).
- Token bucket capacities should align with vendor rate limits (Alpha Vantage 600 cpm, IBKR pacing).
- Rotation groups must respect API constraints (IBKR Level-2 max 3 concurrent). Scheduler enforces via
  rotation windows and pluggable cadence.
- Jitter recommended for bursty jobs to avoid thundering herd on restart.

### Implementation Checklist
- [ ] Implement CLI commands (`snapshot`, `tail`, `dispatch`, `reload`, `pause/resume`).
- [ ] Ensure `persist_scheduler_state()` executed on normal shutdown and during periodic loop.
- [ ] Add unit tests for cron parsing with jitter, token bucket consumption, rotation pointer persistence.
- [ ] Add integration test simulating restart: persist state → reload → verify next runs unchanged.
- [ ] Verify alerts fire by simulating job lag and bucket starvation in staging.
- [ ] Document new jobs in `config/schedule.yml` with owner/contact.

## Observability & Alerting

### Mission & Scope
- Provide cross-module visibility into health, freshness, latency, and error conditions.
- Dispatch actionable alerts to Slack/Telegram/email with severity tags so operators can triage quickly.
- Centralize metrics/logging configuration and expose diagnostic CLI/streams.

### Components & Inputs
| Component | Description | Inputs | Config |
|-----------|-------------|--------|--------|
| Heartbeat monitor | Scheduler job scanning `system:heartbeat:*` | Module heartbeat keys, expected TTLs | `config/observability.yml.heartbeats` |
| Data freshness monitor | Loop verifying `state:ingestion:*` timestamps | Ingestion metadata keys | `config/observability.yml.freshness` |
| Metrics aggregator | Snapshot `metrics:*` → Postgres | Redis hashes `metrics:*` | `config/observability.yml.metrics` |
| Alert dispatcher | Send alerts to Slack/Telegram/email | `stream:alerts` events | `config/observability.yml.alerts`, `.env` tokens |
| Log manager | Structlog + rotating files | Module loggers | `config/logging.yml` |

### Scheduler Jobs & Ownership
| Job | Owner | Cadence | Error budget |
|-----|-------|---------|--------------|
| `observability.heartbeat_monitor` | Scheduler | 15s | 2 misses → `observability_heartbeat_monitor_gap` warning. |
| `observability.freshness_monitor` | Scheduler | 30s | 2 misses → warning. |
| `observability.metrics_aggregator` | Scheduler | 60s | 2 misses → warning. |
| `observability.alert_dispatcher` | Orchestrator task | continuous | Downtime >30s → warning; >2m → page. |

### Heartbeat Monitoring
- TTL expectations configured per module (see `config/observability.yml.heartbeats`):
  ```yaml
  heartbeats:
    analytics_engine: 15
    signal_engine: 15
    execution_engine: 10
    scheduler: 15
    social_hub: 30
    watchdog: 30
  ```
- Monitor marks module `stale` when TTL < 0 or > 2× expected; status stored in `state:health:heartbeats` with
  timestamps.
- `metrics:observability` increments counters (`heartbeat_stale_total`, `heartbeat_recovered_total`).
- Disabled modules flagged `disabled` to avoid false alerts.

### Data Freshness Monitoring
- Checks ingestion keys for age using definitions, e.g.:
  ```yaml
  freshness:
    - key: "raw:alpha_vantage:realtime_options:{symbol}"
      max_age_sec: 45
      symbols: [SPY, QQQ, IWM]
    - key: "raw:ibkr:quotes:{symbol}"
      max_age_sec: 9
      symbols: [SPY, QQQ, IWM]
    - key: "raw:ibkr:l2:{symbol}"
      max_age_sec: 7
      symbols: [SPY, QQQ, IWM]
  ```
- Failing feeds recorded in `state:health:data` with `status` and `age_seconds`.
- Alerts `observability_data_stale` include symbol, feed type, age, expected cadence.
- Monitor respects module feature gates; if ingestion feed disabled, skip check.

### Metrics Aggregator
- Every 60s snapshot `metrics:*` to Postgres `audit.metrics_snapshots` with `env`, `module`, `payload`.
- Aggregation includes derived ratios (e.g., approvals/total signals) for dashboards; retention (default
  30 days) configurable.

### Alert Dispatching
- Modules push alerts to `stream:alerts` with fields `severity`, `module`, `code`, `message`, `event_type`
  (`scheduled`/`replay`), `env`, `correlation_id`.
- Dispatcher enforces cooldowns per alert code (e.g., `execution_slippage_exceeded` 5 min) and dedupes
  repeats within window.
- Severity mapping:
  - `critical` → page on-call (Telegram high priority/SMS).
  - `high` → Slack + Telegram warning.
  - `medium` → Slack warning only.
  - `info` → metrics/log.
- Routing configuration lives in `config/observability.yml`:
  ```yaml
  routing:
    critical: { channels: [telegram, email], cooldown_sec: 60 }
    high:     { channels: [slack, telegram], cooldown_sec: 300 }
    medium:   { channels: [slack], cooldown_sec: 600 }
    info:     { channels: [], cooldown_sec: 0 }
  ```
- Failed deliveries retried x3 with exponential backoff; persistent failure raises
  `observability_dispatch_failure` (critical).
- Alert event schema (stable wire format):
  ```json
  {
    "event": "alert",
    "code": "observability_heartbeat_stale",
    "severity": "high",
    "module": "execution_engine",
    "env": "dev",
    "message": "execution heartbeat stale (ttl=-5s, expected<=10s)",
    "correlation_id": "schd:signal.evaluate.0dte:SPY:2025-09-27T14:10:00Z",
    "context": {"ttl": -5, "expected_ttl": 10, "last_seen": "…"},
    "event_type": "scheduled",
    "ts": "2025-09-27T14:10:05Z",
    "dedupe_key": "observability_heartbeat_stale:execution_engine"
  }
  ````
- Dispatcher writes `state:alerts:cooldown:{dedupe_key}` with configured TTL and stores last payload in
  `state:alerts:last:{dedupe_key}`. If cooldown key exists, alert is suppressed (logged, `alerts_suppressed_total`
  incremented) to avoid storms.

### Logging & Rotation
- Central logging via `structlog` configured in `config/logging.yml`. Default rotation 50 MB × 5 files
  per module under `logs/`.
- Sensitive data redacted by logging processors (API keys, account IDs). New loggers must use
  structured context to avoid leaks.
- CLI `python -m src.tools.tail_logs --module analytics` supports filtering via `jq`.
- Recommended structlog configuration:
  ```python
  import structlog, os, re

  SENSITIVE = re.compile(r"(api[_-]?key|token|secret|bearer)", re.I)

  def redact_sensitive(_, __, event_dict):
      return {k: ("***" if SENSITIVE.search(k) else v) for k, v in event_dict.items()}

  def add_env(_, __, event_dict):
      event_dict["env"] = os.getenv("APP_ENV", "dev")
      return event_dict

  structlog.configure(
      processors=[
          add_env,
          redact_sensitive,
          structlog.processors.TimeStamper(fmt="iso"),
          structlog.processors.dict_tracebacks,
          structlog.processors.JSONRenderer(),
      ]
  )
  ```

### Metrics Namespace
- Standardized hashes:
  - `metrics:analytics`, `metrics:signals`, `metrics:execution`, `metrics:scheduler`, `metrics:observability`, etc.
- Observability aggregator ensures counts monotonic where applicable; gauges recorded separately via
  `metrics:observability:gauges`.
- `metrics:observability` should include counters:
  - `alerts_sent_total{severity,code}`
  - `alerts_suppressed_total{code}`
  - `heartbeat_stale_total{module}`
  - `freshness_violations_total{feed}`
  - `dispatch_fail_total{channel}`

### Failure Modes & Alerts
| Failure | Detection | Automated action | Alert |
|---------|-----------|------------------|-------|
| Heartbeat stale | TTL > 2× expected | Mark stale, enqueue alert | `observability_heartbeat_stale` (high). |
| Freshness violation | Data age exceeds threshold | Mark data `stale`, alert | `observability_data_stale` (high). |
| Alert delivery failure | HTTP/API error after retries | Log and escalate | `observability_dispatch_failure` (critical). |
| Metrics persistence failure | Postgres insert error | Retry once, fallback to Redis-only | `observability_metrics_persist_failed` (medium). |
| Log rotation failure | File handler exception | Attempt reopen, log degraded state | `observability_log_rotation_failed` (medium). |
- On final delivery failure, dispatcher stores payload in `state:alerts:dead_letter:{dedupe_key}` for
  post-mortem review.

### CLI & Diagnostics
| Command | Purpose |
|---------|---------|
| `python -m src.observability.cli heartbeat` | Show heartbeat TTLs/status. |
| `python -m src.observability.cli freshness` | Print freshness summary per feed. |
| `python -m src.observability.cli alerts --since <ISO>` | Stream alert events from `stream:alerts`. |
| `python -m src.observability.cli metrics --module <name>` | Dump metrics hash for module. |
| `python -m src.observability.cli test-alert --code <id>` | Emit test alert through dispatcher. |
| `python -m src.observability.cli dedupe --code <id>` | Inspect cooldown TTL and last payload for `dedupe_key`. |
| `python -m src.observability.cli tailslack` | Stream high/critical alerts for piping to Slack/webhooks. |

### Operational Procedures
- **Heartbeat alert:** inspect module logs, confirm module intentionally halted; restart if unexpected.
- **Data stale alert:** verify ingestion job running, check upstream API status, consider pausing dependent
  signals/execution modules.
- **Alert storm:** adjust cooldowns or severity thresholds; ensure module not flapping (use metrics
  trends). Check `alerts_suppressed_total` counters and adjust `routing.*.cooldown_sec` or widen
  heartbeat/freshness thresholds if modules are flapping.
- **Log overflow:** confirm rotation functioning; adjust rotation size/count as needed.
- **Metrics audit:** query Postgres snapshots to validate pipeline; reconcile with Redis values.

### Implementation Checklist
- [ ] Implement heartbeat, freshness, metrics jobs with configurable cadences and feature gates.
- [ ] Build alert dispatcher integrating Slack/Telegram/email with cooldown/dedupe.
- [ ] Ensure structured logging with redaction processors applied across modules.
- [ ] Provide observability CLI commands (`heartbeat`, `freshness`, `alerts`, `metrics`, `test-alert`).
- [ ] Add integration tests simulating heartbeat expiry, stale data, dispatch failures.
- [ ] Update `config/observability.yml` with thresholds, contacts, and document pipeline.
- [ ] Verify stale heartbeat produces high alert and recovery emits informational `recovered` alert (dedupe cleared).
- [ ] Test cooldown suppression: duplicate alert within cooldown increments `alerts_suppressed_total`.
- [ ] Ensure alerts with `event_type=replay` do not route to social/email channels.

## Social Hub & Watchdog

### Mission & Scope
- Gate every signal through human or automated review before execution to enforce compliance, risk, and narrative guardrails.
- Syndicate trade lifecycle events to Discord, Telegram, Twitter/X, and Reddit while honouring per-channel tiering, rate limits, and redaction rules.
- Provide a single configuration surface for routing, templates, cooldowns, and monetisation experiments so sales copy aligns with live trading telemetry.

### Feature Gates & Modes
| Config flag (`config/runtime.yml`) | Default | Description |
|------------------------------------|---------|-------------|
| `modules.watchdog.enabled` | true | Boots the review service; when false, signal engine skips pending state and auto-approves. **If enabled while Telegram approvals are disabled and no CLI reviewer is configured, watchdog fails closed** (signals remain pending). |
| `modules.watchdog.autopilot_enabled` | false | Enables auto-approval path using LLM scoring; manual Telegram approval remains authoritative. |
| `modules.social.enabled` | false | Disables all outbound publishing; commands become no-ops but log `module_disabled`. |
| `modules.social.discord.enabled` | false | Enables Discord publisher when true and per-tier channels configured. |
| `modules.social.telegram.enabled` | true | Required for approval workflow; if disabled, CLI fallback must be used. |
| `modules.social.twitter.enabled` | false | Toggles Twitter/X posting job. |
| `modules.social.reddit.enabled` | false | Toggles Reddit syndication queue. |

All CLI commands check the corresponding module flag and emit `module_disabled` audit events before returning without side effects.

### Event Inputs & Storage Contracts
| Source | Key / Stream | TTL | Notes |
|--------|--------------|-----|-------|
| Signal engine pending payload | `signal:pending:{signal_id}` | 30m | Watchdog claims jobs from here, updates `watchdog_status`. |
| Watchdog review artefact | `watchdog:review:{signal_id}` | 2h | JSON bundle with `status`, reviewer, rationale, scoring. |
| Approval audit stream | `stream:watchdog` | stream | Append-only; consumers build dashboards. |
| Telegram approval queue | `state:watchdog:pending_telegram` | 70s | Tracks outstanding approvals to enforce 60s SLA + 10s grace. |
| Social dispatch queue | `queue:social:{channel}` | persistent | Per-channel FIFO (Discord premium/basic/free, Telegram broadcast, Twitter, Reddit). |
| Social cooldown ledger | `state:social:cooldown:{channel}:{tier}` | variable | Stores per-channel cooldown timers derived from rate limits. |
| Template registry | `state:social:templates` | persistent | Latest template hash + checksum for cache busting. |

**Deterministic event IDs:** all social/workflow artefacts use `event_id = sha256(env|event|trade_id|ts_floor)` to guarantee idempotency. The same `event_id` is reused for `social:payload:{event_id}`, `social:sent:{channel}:{event_id}`, stored alongside dispatch metadata, and set on each `stream:social` entry.

### Watchdog Workflow
1. Scheduler fires `watchdog.review.dequeue` every 5s; worker pops signals sorted by creation time.
2. Worker gathers analytics snapshot, risk summary, and account context; runs prompt (manual context) if autopilot enabled.
3. Manual mode (default):
   - Worker posts concise summary to Telegram reviewer channel via `watchdog.pending` template.
   - Reviewers respond within 60s using `/approve <signal_id>` or `/reject <signal_id>`. Absence of reply triggers auto-cancel.
4. Approval writes `signal:approved:{signal_id}` and emits `watchdog.approved`; rejection updates `signal:pending` status and logs reason.
5. Autopilot (optional) uses LLM scoring to pre-classify. Thresholds: `score ≥ 0.85` auto-approves (unless strategy flagged `manual_only`); `0.65 ≤ score < 0.85` leaves pending with LLM rationale; `< 0.65` auto-rejects but allows manual override.
6. SLA monitor job (`watchdog.pending.guard`) scans `signal:pending` older than 60s, issues `/cancel`, sets `watchdog:review:{signal_id}.status=expired`, and increments metrics. When a review expires, the bot sends a single consolidated "expired" message (replying to the original request) so reviewers are notified without spam.

### Prompt Templates & LLM Plan
- Templates live under `templates/watchdog/`; use strict `jinja2` rendering in CI to ensure variables resolved.
- Required files:
  - `templates/watchdog/prompt_core.j2`: deterministic scoring prompt for autopilot.
  - `templates/watchdog/summary_markdown.j2`: summary posted into Telegram.
  - `templates/watchdog/slack_incident.j2`: optional escalation format.
- Recommended OpenAI model: `gpt-4.1-mini` with `temperature=0.1`, `max_tokens=300`. Configure in `config/watchdog.yml`:
  ```yaml
  llm:
    provider: openai
    model: gpt-4.1-mini
    max_tokens: 300
    temperature: 0.1
    api_key_env: OPENAI_API_KEY
  ```
- Prompt snippet (core scoring):
  ```text
  You are the compliance reviewer for intraday options signals. Rate the proposed trade from 0 to 1.
  Use the analytics bundle, risk summary, and current exposure details provided.
  Never approve if risk caps or cooldowns are violated. Respond as JSON:
  {"score": <0-1>, "reason": "short bullet"}
  ```
- LLM responses must validate against JSON schema before use; validation failures fall back to manual review and raise `watchdog_autopilot_error`.

### Approval Commands (Telegram)
- `/approve <signal_id> [reason]`
- `/reject <signal_id> <reason>` (reason mandatory for audit trail).
- `/snooze <signal_id> <minutes>` defers SLA timer (writes `state:watchdog:snooze:{signal_id}`).
- `/force <signal_id>` overrides autopilot rejection (requires `watchdog.override` role).

Bot enforces 1 request per second per chat and 20 messages per minute per group to stay within Telegram limits.[^telegram_limits]

### Social Channel Matrix
| Channel | Tier / Audience | Trigger | Delay | Template | Sensitive fields removed |
|---------|-----------------|---------|-------|----------|--------------------------|
| Discord | Premium | `trade.opened`, `trade.scale_*`, `trade.closed` | 0s | `templates/social/discord/premium_trade.md` | Account numbers, order IDs, IBKR account aliases. |
| Discord | Basic | Same events | 60s after first IBKR fill | `templates/social/discord/basic_trade.md` | As above, plus position size bucketed. |
| Discord | Free | `trade.closed` only | 300s after close | `templates/social/discord/free_digest.md` | PnL rounded to nearest $10, no sizing. |
| Discord | Market Analysis (Premium) | Scheduled 08:45, 12:30, 16:10 ET | 0s | `templates/social/discord/premium_market.md` | Removes raw analytics IDs; includes CTA footers. |
| Discord | Market Analysis (Basic) | 12:30 ET | 0s | `templates/social/discord/basic_market.md` | No proprietary factor weights. |
| Discord | Market Analysis (Free) | 16:30 ET | 0s | `templates/social/discord/free_market.md` | High-level bullet list only. |
| Telegram | Portfolio digest | `trade.closed`, daily 17:00 ET account snapshot | 0s | `templates/social/telegram/daily_digest.md` | Summaries only, env tag added. |
| Twitter/X | Public teaser | `trade.closed` where PnL ≥ threshold | 90s | `templates/social/twitter/trade_teaser.md` | Delta anonymised, PnL banded. |
| Reddit | Public recap | Daily 18:00 ET aggregated performance | 0s | `templates/social/reddit/daily_thread.md` | Aggregated stats, no symbol sizing. |

Queue workers enforce per-channel delays by scheduling jobs via Redis sorted sets (`queue:social:scheduled`) and only promoting to live queue when delay elapsed.

**Back-pressure management:** each `queue:social:{channel}` enforces a configurable hard ceiling. When depth exceeds the ceiling, dispatcher raises `social_queue_depth_high`, evicts lowest-priority scheduled items first (logging `dropped_due_to_backpressure`), and records payloads in `state:social:dead_letter:{channel}:{event_id}` with the last error context. Operators can inspect drains via `python -m src.social.cli deadletters --channel <name>`.

### Rate Limits & Token Buckets
| Platform | Constraint | Implementation |
|----------|------------|----------------|
| Discord | Global 50 requests/sec per bot token; invalid requests capped at 10,000 per 10 minutes.[^discord_limits] | `buckets.discord.global` capacity 50, refill 50/sec; shared bucket for all REST calls. Track invalid responses to avoid Cloudflare bans. |
| Discord | Per-route limits vary (e.g., message create ~5 per 5s per channel). Clients must inspect `X-RateLimit-*` headers.[^discord_limits] | Maintain per-channel token bucket `buckets.discord.channel:{channel_id}` using header metadata. |
| Telegram | Free broadcast limit ≈ 30 msgs/sec; 1 msg/sec per chat; group limit 20 msgs/min; paid broadcasts up to 1000 msgs/sec.[^telegram_limits] | Separate buckets for approvals (per chat) and broadcasts. Paid tier flag switches to high-throughput bucket. |
| Twitter/X | Posts capped at 2,400 per account per day (~300 per 3h window). Reposts count toward quota.[^x_limits] | `buckets.twitter.post` capacity 300, refill every 3h. Pause queue when daily usage ≥75%. |
| Reddit | OAuth clients may make up to 60 requests per minute.[^reddit_limits] | `buckets.reddit.api` capacity 60, refill 60/min; aggregate comment + flair updates. |

Rate-limit configuration stored in `config/social.yml` so environments can dial volumes independently.

For Discord, capture every response's `X-RateLimit-*` headers and persist to `state:social:discord:route_limits:{channel_id}` (fields: `reset_at`, `remaining`, `bucket_id`). Dispatchers consult this cache to pre-empt sends when remaining ≤1 even before a 429 occurs.

### Publishing Pipeline
1. Execution emits lifecycle events to `stream:trades`; analytics emits daily summaries.
2. Social aggregator enriches events, storing rendered payload drafts at `social:payload:{event_id}` (TTL 2h).
3. Formatter selects template, renders Markdown/embeds, and validates platform constraints (Discord embed size, Telegram 4096-char limit).
4. Dispatcher dequeues respecting token buckets; on 429, delays per `Retry-After` and retries with exponential backoff (max 5 attempts). Dispatches tagged `event_type=replay` are prevented from reaching public channels (Discord free/basic, Twitter, Reddit); they are delivered to internal Slack/Telegram diagnostics only.
5. Successful posts recorded in `social:sent:{channel}:{event_id}` (TTL 7d) and appended to `stream:social`; duplicates skipped using deterministic `event_id`.

### Failure Handling & Retries
| Failure | Detection | Automated action | Alert |
|---------|-----------|------------------|-------|
| Telegram approval timeout | `watchdog.pending.guard` finds >60s pending | Auto-cancel + notify reviewers | `watchdog_pending_timeout` (high). |
| Telegram bot 429 | API response 429 | Backoff 3s, retry 5x; escalate to backup bot token | `watchdog_telegram_ratelimit` warning. |
| Discord publish 429 | API headers show bucket exhausted | Delay per `Retry-After`, requeue; pause channel 60s after 3 consecutive 429s | `social_discord_ratelimit` warning. |
| LLM failure / malformed JSON | Schema validation error | Switch signal to manual review | `watchdog_autopilot_error` medium. |
| Template rendering error | Jinja exception | Mark dispatch failed, alert template maintainer, skip channel | `social_template_error` high |
| Posting cooldown breach | Duplicate `event_id` in `social:sent:*` | Skip send, increment `social_posts_suppressed_total` | none (metric only). |
| Queue overflow | `queue:social:{channel}` depth > ceiling | Raise `social_queue_depth_high`, drop lowest priority jobs to dead-letter store | `social_queue_depth_high` warning |

Dispatcher writes `state:alerts:last:{dedupe_key}` and honours cooldowns consistent with observability runbook.

### Observability
- Heartbeats: `system:heartbeat:watchdog` TTL 10s, `system:heartbeat:social_hub` TTL 10s.
- Metrics: `metrics:watchdog` (`pending_total`, `auto_cancelled_total`, `autopilot_score_bucket{band}`), `metrics:social` (`posts_sent_total{channel,tier}`, `posts_suppressed_total{reason}`, `rate_limit_total{platform}`), `social_latency_seconds` histogram (signal close → publish).
- Alerts:
  - `watchdog_sla_breach` (pending >90s).
  - `social_dispatch_stalled` (no premium posts during market hours while trades active).
  - `social_queue_depth_high` (scheduled queue depth above threshold).

### CLI & Diagnostics
- `python -m src.watchdog.cli stats` → prints pending count, average SLA breach, autopilot score histogram.
- `python -m src.social.cli deadletters --channel <name>` → inspects `state:social:dead_letter:{channel}:*` entries and outputs payload + last error.
- `python -m src.social.cli resend --event-id <id> --channel <name>` → loads `social:payload:{event_id}`, clones metadata with new dispatch ID, and replays respecting token buckets.

### Monetisation Hooks & Ideas
- Premium upsell banner appended to free/basic market analysis messages (toggle via `config/social.yml.promotions.enabled` with per-channel/tier allowlists and a configurable `daily_cap_per_channel`).
- A/B test CTA copy by specifying `template_variant` per guild and logging conversions via vanity URLs.
- Offer “alert replay” packs so premium users can request last five premium alerts via Discord slash command (rate-limited to once per hour).
- Capture engagement metrics (reactions, clicks) where APIs allow and store under `social:engagement:{event_id}` for churn modelling.

### Configuration References
`config/watchdog.yml` (example):
```yaml
telegram:
  approvals_channel_id: -123456789  # reviewers group chat
  bot_token_env: WATCHDOG_TELEGRAM_TOKEN
  reviewer_roles:
    default: ["lead_trader", "risk_officer"]
    override: ["principal"]
sla:
  seconds: 60
  expired_template: watchdog/expired_notice.md
autopilot:
  enabled: false
  model_alias: gpt-4.1-mini
  approve_threshold: 0.85
  manual_threshold: 0.65
  prompt_template: watchdog/prompt_core.j2
fallbacks:
  require_manual_if:
    - key: analytics.quality.overall
      value: degraded
    - key: risk.daily_loss_halt
      value: true
```

`config/social.yml` (example excerpt):
```yaml
features:
  enabled: false
  channels:
    discord: {enabled: true}
    telegram: {enabled: true}
    twitter: {enabled: false}
    reddit: {enabled: false}
discord:
  guilds:
    premium:
      channel_id: 1122334455
      tiers: [premium]
    basic:
      channel_id: 2233445566
      tiers: [basic]
    free:
      channel_id: 3344556677
      tiers: [free]
  token_env: DISCORD_BOT_TOKEN
  queue_ceiling: 200
telegram:
  broadcast_chat_id: -99887766
  queue_ceiling: 150
  approvals_chat_id: -123456789
promotions:
  enabled: true
  daily_cap_per_channel: 3
  allowlists:
    discord:
      premium: false
      basic: true
      free: true
  template: social/promotions/upgrade_cta.md
rate_limits:
  twitter_daily_cap: 600  # stop early if close to 2,400/day hard cap
  backpressure:
    low_priority_drop_threshold: 0.8
```

### Implementation Checklist
- [ ] Implement Telegram bot commands with role-based ACL and 60s SLA enforcement.
- [ ] Build LLM client with schema validation, retries, and feature gate toggle.
- [ ] Create template set under `templates/social/` with lint job ensuring placeholders resolved.
- [ ] Implement rate-limit aware dispatchers per platform with token bucket config.
- [ ] Add metrics/alerts described above and wire into observability dispatcher.
- [ ] Write integration tests for approval timeout, LLM rejection, Discord 429, queue back-pressure, and monetisation toggles.
- [ ] Document onboarding steps for Discord tiers (channel IDs, webhook secrets) in `config/social.yml.example`.
- [ ] Validate data sanitisation (no account identifiers, env tags present) via automated redaction tests.

[^discord_limits]: Discord API rate limits and global 50 req/s guidance — https://raw.githubusercontent.com/discord/discord-api-docs/main/docs/topics/rate-limits.md
[^telegram_limits]: Telegram bot broadcast limits — https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this
[^x_limits]: X (Twitter) post limits — https://r.jina.ai/https://help.x.com/en/rules-and-policies/twitter-limits
[^reddit_limits]: Reddit OAuth client rate limit — https://r.jina.ai/https://github.com/reddit-archive/reddit/wiki/API#rules

## Dashboard & Reporting

### Mission & Scope
- Deliver a single-pane-of-glass showing live trading posture, performance, and system health for operators, PMs, and stakeholders.
- Provide scheduled reports (PDF/CSV) and ad-hoc exports that reconcile with source-of-truth metrics in Redis/Postgres.
- Surface leading indicators (risk, liquidity, engagement) fast enough to inform intraday decisions while preserving historical snapshots for audits.

### Feature Gates & Modes
| Config flag (`config/runtime.yml`) | Default | Description |
|------------------------------------|---------|-------------|
| `modules.reporting.enabled` | false | Enables dashboard API + refresh workers. When false, UI serves maintenance state and snapshot jobs are paused. |
| `modules.reporting.pdf_exports` | false | Toggles scheduled PDF generation; keep off until wkhtmltopdf stack validated. |
| `modules.reporting.csv_exports` | true | Allows CSV download endpoints (adhere to role ACL). |
| `modules.reporting.realtime_tiles` | true | Streams tile updates via WebSocket/SSE when analytics cadence supports it. |
| `modules.reporting.anonymise_public` | true | Redacts position sizes before presenting to external tier dashboards. |

Reporting module fails closed: if `modules.reporting.enabled=true` but required caches/warehouse pools unavailable, refresh jobs set dashboard status `degraded` and UI returns 503 with maintenance message.

### Data Inputs & Storage Contracts
| Source | Access pattern | Storage key / table | TTL / retention | Notes |
|--------|----------------|----------------------|-----------------|-------|
| Analytics bundles | Redis read | `derived:analytics:{symbol}` | 20s | Used for intraday exposure, vol, liquidity tiles. |
| Risk summaries | Redis read | `derived:risk_summary:{symbol}` | 20s | Feed risk dashboard and daily VaR computation. |
| Signal & trade history | Postgres | `trading.signals`, `trading.trades`, `trading.execution_events` | 7y retention | Primary source for performance & attribution. |
| Metrics snapshots | Postgres | `audit.metrics_snapshots` | 30d (configurable) | Populated by observability aggregator; used for trend charts. |
| Social engagement | Redis hash | `social:engagement:{event_id}` | 14d | Drives subscriber analytics. |
| SLO counters | Redis hash | `metrics:observability` et al. | 1d | Feed operational dashboards. |
| Reference data | Postgres | `reference.symbols`, `reference.accounts` | persistent | Symbol metadata, account groupings. |
| Export cache | Redis | `reporting:exports:{dashboard}:{date}` | 24h | Stores generated files metadata prior to S3 upload. |

Derivations and aggregates publish to Redis `dashboard:tiles:{dashboard}` (JSON payload, TTL 60s) and persist audited snapshots to Postgres `reporting.tiles` (columns: `dashboard`, `tile_id`, `payload`, `captured_at`).

### Dashboard Catalogue
| Dashboard | Audience | Contents | Refresh cadence | Access |
|-----------|----------|----------|-----------------|--------|
| Executive Overview | Founders / stakeholders | Net PnL, win-rate trend, capital utilisation, top strategies, macro overlays | 5 min during trading hours | `role:executive` |
| Trading Ops Console | Desk operators | Live exposures, open positions, pending signals, execution latency, alert feed | 20s | `role:operator` |
| Risk & Compliance | Risk officer | VaR, delta/gamma buckets, drawdown heatmap, watchdog SLA, halt status | 60s | `role:risk` |
| Subscriber Engagement | Product/marketing | Premium vs basic retention, notification latency, social conversions | 15 min | `role:product` |
| Post-session Report | Stakeholders | Daily recap, realized PnL attribution, macro narrative, social reach summary | Generated 16:30 ET | PDF/CSV emailed |

Dashboard definitions live in `config/dashboard.yml` with per-tile SQL/Redis queries, refresh cadences, ACLs, and anonymisation flags.

### Refresh Pipeline & Scheduler Jobs
| Job ID | Cadence | Inputs | Output | Notes |
|--------|---------|--------|--------|-------|
| `reporting.refresh.ops_console` | 20s | Analytics bundles, execution queues | `dashboard:tiles:ops_console` | Runs only when `modules.reporting.realtime_tiles` true. |
| `reporting.refresh.exec_overview` | 5 min | Metrics snapshots, trade history | `dashboard:tiles:exec_overview` | Aggregates intraday metrics and writes Postgres snapshot. |
| `reporting.refresh.risk` | 60s | Risk summaries, account snapshots | `dashboard:tiles:risk` | Validates exposures vs limits; marks tile `warning` if thresholds crossed. |
| `reporting.refresh.engagement` | 15 min | Social engagement hashes, subscriber DB | `dashboard:tiles:engagement` | Applies tier-specific redaction. |
| `reporting.export.daily_pdf` | 16:35 ET | Exec overview tiles, commentary templates | `reporting:exports:daily:{date}` + S3 upload | Requires `modules.reporting.pdf_exports`. |

Jobs run through scheduler token bucket `reporting_refresh` (default 10 jobs/min) to avoid contention. Each job writes heartbeat `system:heartbeat:reporting:{dashboard}` (TTL 2× cadence).

### Rendering & Delivery
1. Refresh job computes tiles using data loaders + SQL templates defined in `config/dashboard.yml`.
2. Tile payload structure (bounded to `max_payload_kb`, default 128 KB):
   ```json
   {
     "tile_id": "ops.latency",
     "status": "ok|warning|error",
     "serving_version": 42,
     "is_stale": false,
     "ttl": 60,
     "render": {"type": "timeseries", "data": [...]},
     "sources": ["metrics:execution", "stream:alerts"],
     "captured_at": "2025-09-27T14:20:02Z"
   }
   ```
3. Tiles pushed to Redis list `dashboard:tiles:{dashboard}` and WebSocket topic `ws://.../dashboard/{dashboard}` if realtime enabled.
4. React UI polls WebSocket with HTTP fallback; server caches 3 generations to allow lightweight diffing.
5. Export workers assemble PDFs/CSVs using stored tiles + markdown narrative templates (`templates/reporting/daily_summary.md`), uploading to S3 bucket `s3://quanticity-reporting/{env}/` with 90-day TTL (configurable). CSV exports record a schema hash at `reporting:exports:schema_hash:{dashboard}` so downstream diffs ignore pure column-order changes.

### Access Control & Redaction
- API gateway enforces JWT scopes (`dashboard:exec`, `dashboard:ops`, etc.) before returning tiles or exports.
- Public tiers (`anonymise_public=true`) strip contract sizes, account IDs, and bucket PnL to ranges before rendering.
- Requests without role fallback to summary view with limited tiles.

### Failure Modes & Handling
| Failure | Detection | Automated action | Alert |
|---------|-----------|------------------|-------|
| Tile refresh timeout | Job exceeds `max_runtime` (default 8s) | Abort run, keep previous tile, set status `stale` | `reporting_refresh_timeout` warning |
| Data source stale | Input freshness check fails | Mark tile `warning`, embed diagnostic in tile payload | `reporting_source_stale` warning |
| Export generation error | PDF/CSV renderer exception | Retry 2×; on failure store payload in `state:reporting:dead_letter:{date}` | `reporting_export_failed` high |
| WebSocket back-pressure | Subscriber count > threshold | Auto-downgrade to HTTP polling, log event | `reporting_realtime_disabled` info |
| Warehouse connectivity loss | Postgres pool error | Trip circuit breaker, stop jobs, set dashboard `degraded` | `reporting_warehouse_down` high |

Dead-letter entries include payload and stack trace for replay via CLI.

### Observability & Metrics
- Heartbeat per dashboard: `system:heartbeat:reporting:{dashboard}` TTL `cadence × 2`.
- Metrics namespace `metrics:reporting` tracks:
  - `tiles_refreshed_total{dashboard}`
  - `refresh_latency_ms_bucket`
  - `tiles_status_total{dashboard,status}`
  - `exports_generated_total{format}`
  - `exports_failed_total{format}`
- Alerts integrate with observability dispatcher using codes above; severity defaults configurable in `config/reporting.yml.alerts`.

### CLI & Diagnostics
- `python -m src.reporting.cli refresh --dashboard ops_console` → forces immediate tile recomputation.
- `python -m src.reporting.cli status` → prints heartbeat age, last refresh duration, tile counts per dashboard.
- `python -m src.reporting.cli export --date 2025-09-27 --format pdf` → regenerates daily report and uploads.
- `python -m src.reporting.cli deadletters --since <ISO>` → dump export failures from `state:reporting:dead_letter:*`.
- `python -m src.reporting.cli compare --dashboard exec_overview --window 7d` → compares tile values against Postgres snapshots for drift detection.

CLI guards:
- PDF exports in production (`APP_ENV=prod`) require `CONFIRM=YES` environment variable to prevent accidental mass notifications.
- Drift comparison writes a JSON explainer to `reporting:compare:last:{dashboard}` (fields: `tile_id`, `baseline_value`, `current_value`, `explanation`) whenever thresholds breached, enabling post-mortems.

### Configuration Reference
`config/dashboard.yml` (excerpt):
```yaml
defaults:
  timezone: America/New_York
  anonymise_public: true
dashboards:
  ops_console:
    enabled: true
    cadence_sec: 20
    roles: [operator]
    tiles:
      - id: ops.pending_signals
        source: sql:reporting/sql/pending_signals.sql
        max_runtime_ms: 4000
        warn_threshold:
          value: 3
          comparator: ">="
      - id: ops.execution_latency
        source: redis:metrics:execution
        transform: reporting.transforms.latency_timeseries
  exec_overview:
    enabled: true
    cadence_sec: 300
    roles: [executive, risk]
    tiles:
      - id: pnl.daily_curve
        source: sql:reporting/sql/daily_pnl.sql
        anonymise: false
      - id: liquidity.health
        source: redis:derived:liquidity
exports:
  daily_pdf:
    enabled: false
    template: templates/reporting/daily_summary.md
    deliver:
      email: ["founder@quanticity.com"]
      slack_webhook: ${REPORTING_SLACK_WEBHOOK}
```

### Implementation Checklist
- [ ] Build dashboard refresh workers honouring `config/dashboard.yml` cadences and role ACLs.
- [ ] Implement tile transformers (Redis + SQL) with schema validation and unit tests.
- [ ] Wire WebSocket/SSE backend with fallback polling and load-test for 500 concurrent subscribers.
- [ ] Implement export pipeline (PDF/CSV) with retry, dead-letter queue, and S3 retention policy.
- [ ] Integrate reporting metrics with observability (`metrics:reporting`, alert codes).
- [ ] Add regression tests comparing dashboard tiles versus known fixtures for analytics/risk metrics.
- [ ] Document onboarding steps for new dashboards (tile definition, ACL, promotion to staging/prod).
- [ ] Provide data reconciliation script to validate Postgres snapshots vs dashboard output nightly.
- [ ] Enforce per-tile `max_payload_kb` and include `serving_version`/`is_stale` fields in tile schema.
- [ ] Persist export schema hashes and drift explainers (`reporting:compare:last:*`) for auditability.

## Upcoming Guides
- To be defined. Add new entries here as additional runbooks are scoped.

Track progress in `docs/README.md` as sections graduate from draft to complete playbooks.
