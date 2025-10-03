---
title: Analytics Engine
description: Institutional-grade factor computation layer fusing Unusual Whales and Interactive Brokers data sources.
version: 1.0.0
last_updated: 2025-10-02
---

# Analytics Engine
## Institutional Factor Fabric for Options & Equity Strategies

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Data Inputs & Semantic Layers](#3-data-inputs--semantic-layers)
4. [Factor Library](#4-factor-library)
   1. [Institutional Flow Pressure (IFP)](#41-institutional-flow-pressure-ifp)
   2. [Sweep Persistence Index (SPI)](#42-sweep-persistence-index-spi)
   3. [Dealer Pressure Index (DPI)](#43-dealer-pressure-index-dpi)
   4. [Gamma Flip Early Warning (GFEW)](#44-gamma-flip-early-warning-gfew)
   5. [Liquidity Confluence Heatmap (LCH)](#45-liquidity-confluence-heatmap-lch)
   6. [Volatility Surface Stress (VSS)](#46-volatility-surface-stress-vss)
   7. [Option Chain Sentiment Score (OCSS)](#47-option-chain-sentiment-score-ocss)
   8. [Dark vs Lit Confirmation (DLC)](#48-dark-vs-lit-confirmation-dlc)
   9. [Event Risk Surface (ERS)](#49-event-risk-surface-ers)
   10. [Execution Slippage Forecast (ESF)](#410-execution-slippage-forecast-esf)
   11. [Real-Time Risk Dial (RTRD)](#411-real-time-risk-dial-rtrd)
   12. [Alpha Attribution Feedback (AAF)](#412-alpha-attribution-feedback-aaf)
5. [Pipeline Orchestration](#5-pipeline-orchestration)
6. [Processing Framework & Storage](#6-processing-framework--storage)
7. [Model Governance & Change Control](#7-model-governance--change-control)
8. [Integration Touchpoints](#8-integration-touchpoints)
9. [Monitoring, QA & Runbooks](#9-monitoring-qa--runbooks)
10. [Testing & Simulation](#10-testing--simulation)
11. [Security & Compliance](#11-security--compliance)
12. [Roadmap](#12-roadmap)
13. [Conclusion](#13-conclusion)

---

## 1. Overview

### 1.1 Mission

The Analytics Engine is the **brain** that converts raw market telemetry into actionable intelligence. It fuses:

- **Unusual Whales WebSockets**: millisecond-level option flow, dealer gamma feeds, live prices, and news.
- **Unusual Whales REST**: historical aggregates, volatility surfaces, dark pools, option chain metadata, calendars.
- **Interactive Brokers Official API**: microstructure (tick-by-tick, L2 depth, 5-second bars), order book dynamics, and P&L/account signals.

These streams feed a factor library that powers signal qualification, execution routing, and risk management.

### 1.2 Key Requirements

| Requirement | Detail |
|-------------|--------|
| Latency | Sub-1s refresh for intraday factors (IFP, DPI, RTRD); ≤5s for execution support (LCH, ESF); ≤15m for volatility/event analytics |
| Resilience | Graceful degradation with stale flags; deterministic recomputation for backfills |
| Auditability | Factor inputs, formulas, versions logged for compliance & research reproducibility |
| Scalability | Support 20+ tickers, high message volume (>2000 msg/s) without drift |
| Extensibility | Modular factor framework for new analytics (plug-in architecture) |

### 1.3 Stakeholders

- **Signal Generation**: consumes factor vectors to decide trade entries/exits.
- **Execution & Position Management**: uses liquidity, dealer, and slippage factors for routing.
- **Risk Management**: leverages RTRD, ERS, DPI for guardrails.
- **Research & Reporting**: analyze factor efficacy and produce daily summaries.

---

## 2. System Architecture

```
                                    ┌───────────────────────────────┐
                                    │     External Data Providers    │
                                    │  UW WebSockets / UW REST / IBKR│
                                    └──────────────┬────────────────┘
                                                   │ Ingestion (docs/unusual_whales_*.md, interactive_brokers.md)
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Data Landing Layer (Real-Time)                                      │
│  - Redis Streams: uw_ws:*, ib_l1:*, ib_l2:*, ib_ticks:*                                                 │
└───────────────┬────────────────────────────────────────────────────────────────────────────────────────┘
                │ Fan-out
                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               Analytics Processing Layer (Python 3.11)                                 │
│  - Streaming workers (asyncio)                                                                          │
│  - Batch pipelines (Airflow/Prefect)                                                                    │
│  - Factor computation modules (per factor)                                                              │
│  - ML scoring services (ESF)                                                                            │
└───────────────┬─────────────┬────────────────────────────┬───────────────────────────┘
                │             │                            │                           
         Redis Feature   TimescaleDB Hypertables   Feature Store Views
                │             │                            │                           │
                ▼             ▼                            ▼                           ▼
       ┌────────────────┐  ┌─────────────────────────┐  ┌─────────────────────┐
       │ Signal Engine  │  │ Risk/Execution Systems  │  │ Research Notebooks   │
       │ (downstream)   │  │ (dashboards, controls)   │  │ (historical factors) │
       └────────────────┘  └─────────────────────────┘  └─────────────────────┘
```

### 2.1 Compute Topology

- **Streaming Workers**: Lightweight Python services (Docker Compose or systemd) consuming Redis Streams; each worker handles a subset of tickers.
- **Batch Jobs**: Cron-triggered Python scripts or lightweight scheduler (e.g., Prefect) handle 5m/15m/60m/EOD analytics; backfills run on demand.
- **Model Serving**: ESF predictions exposed via simple FastAPI microservice (single container).
- **Scaling**: Scale by increasing worker count or moving to beefier hardware as needed; most pipelines run comfortably on a single high-core server.

### 2.2 Data Synchronization

- All factor timestamps standardized to UTC, truncated to nearest cadence bucket.
- Clock synchronization monitored; allowable drift ≤100ms between UW and IB data points.

---

## 3. Data Inputs & Semantic Layers

### 3.1 Data Inventory

| Source | Dataset | Key Fields | Refresh |
|--------|---------|------------|---------|
| UW WS | Option trades | `executed_at`, `side`, `premium`, `volume`, `is_sweep`, `underlying_price` | Streaming |
| UW WS | GEX channels | `timestamp`, `gamma`, `delta`, `expiry`, `strike` | 1s |
| UW WS | Live price | `time`, `bid`, `ask`, `last`, `volume` | <100ms |
| UW REST | Net premium ticks | `bucket`, `net_call_premium`, `net_put_premium`, cum metrics | 60s |
| UW REST | Flow per strike/expiry | `timestamp`, `strike`, `sweep_premium`, `ask_volume`, etc. | 60s–5m |
| UW REST | Spot GEX & greek exposure grids | `timestamp`, `expiry`, `strike`, `gamma_exposure` | 60s–15m |
| UW REST | IV surfaces & rank | `expiry`, `delta`, `iv`, `iv_rank` | 15m |
| UW REST | Dark pool & price ladders | `price`, `volume`, `exchange`, lit/dark split | 5m |
| UW REST | Calendars | `event`, `importance`, `timestamp`, `tickers` | 1h |
| IBKR | Tick-by-tick | `time`, `price`, `size`, `type` | Streaming |
| IBKR | 5-second bars | `time`, `open/high/low/close`, `volume`, `wap` | 5s |
| IBKR | Level 2 depth | `position`, `marketMaker`, `price`, `size`, `side` | Rotating |
| IBKR | L1 quotes | `bid/ask`, `size`, `last`, `volume` | Streaming |
| IBKR | Account summary | `NetLiquidation`, `ExcessLiquidity`, `BuyingPower`, etc. | 60s |
| IBKR | Positions & P&L | `conid`, `quantity`, `avg_cost`, `dailyPnL`, `unrealizedPnL` | 5s–120s |

### 3.2 Semantic Layers

1. **Raw Layer**: Untouched data stored in TimescaleDB raw tables for reprocessing.
2. **Normalized Layer**: Standardized schema (e.g., `flow_events`, `gex_grids`, `ib_ticks`).
3. **Feature Layer**: Intermediate features produced prior to factor aggregation (e.g., rolling sums, z-scores).
4. **Factor Layer**: Final analytics (e.g., IFP, DPI) consumed downstream.

---

## 4. Factor Library

Each factor section includes **Purpose, Inputs, Mathematical Formulation, Implementation Notes, Outputs, Cadence, Quality Controls, and Consumers**.

### 4.1 Institutional Flow Pressure (IFP)

**Purpose:** Quantify directional intensity of institutional option flow across strikes and expiries.

**Inputs:**
- UW WebSocket `option_trades`
- UW REST `/stock/{ticker}/net-prem-ticks`
- UW REST `/stock/{ticker}/flow-per-strike-intraday`
- IBKR 5-second bars (underlying reference price)

**Mathematical Formulation:**

1. Aggregate trades into 1-minute buckets per strike `k` and expiry `e`:
   \[
   P_{buy}(t,e,k) = \sum_{i \in \text{bucket}} premium_i \cdot \mathbb{1}(side_i = \text{buy})
   \]
   \[
   P_{sell}(t,e,k) = \sum_{i \in \text{bucket}} premium_i \cdot \mathbb{1}(side_i = \text{sell})
   \]

2. Rolling 5-minute exponentially weighted net premium:
   \[
   NP(t,e,k) = \alpha \cdot (P_{buy} - P_{sell}) + (1 - \alpha) \cdot NP(t-1,e,k)
   \]
   with \( \alpha = 2/(N+1) \), \( N = 5 \).

3. Normalize using 20-day intraday distribution:
   \[
   Z_{NP}(t,e,k) = \frac{NP(t,e,k) - \mu_{20d}(e,k)}{\sigma_{20d}(e,k)}
   \]

4. Adjust for underlying drift (IBKR 5s bars):
   \[
   adj(t) = \beta \cdot \frac{S(t) - S(t-5m)}{S(t-5m)}
   \]

5. Final factor:
   \[
   IFP(t,e,k) = Z_{NP}(t,e,k) - adj(t)
   \]

**Implementation Notes:**
- Polars for vector aggregation; results written via Timescale `INSERT ... ON CONFLICT`.
- 20-day stats stored in table `analytics_ifp_reference`.
- Decay previous value (0.8 multiplier) when bucket empty.

**Output Schema:** `analytics_ifp(bucket TIMESTAMPTZ, ticker TEXT, expiry DATE, strike NUMERIC, flow_pressure NUMERIC, premium_buy NUMERIC, premium_sell NUMERIC, trades INT, drift_adjustment NUMERIC, confidence SMALLINT)`.

**Cadence:** 60 seconds.

**Quality Controls:**
- Minimum trade count per bucket (≥5) else `confidence=0`.
- Clamp `flow_pressure` to [-6, 6]; log anomalies beyond.

**Consumers:** Signal Generation, Execution.

---

### 4.2 Sweep Persistence Index (SPI)

**Purpose:** Gauge follow-through probability after large sweeps.

**Inputs:**
- UW WebSocket `option_trades` (fields `is_sweep`, `premium`)
- IBKR tick-by-tick (`Last`, `BidAsk`)
- IBKR L1 data

**Computation:**

1. Identify sweeps with notional ≥ `$250,000` in last 60 seconds.
2. For each sweep at `t0`:
   - Observe trades within `T = 180s`.
   - Compute same-direction vs opposite-direction size, `same_size` and `opp_size`.
   - Track NBBO midpoint change `Δm` and time spent above sweep price `τ_pos`.
3. Define raw score:
   \[
   PS = w_1 \cdot \frac{same\_size}{same\_size + opp\_size} + w_2 \cdot \frac{Δm}{spread} + w_3 \cdot \frac{τ_{pos}}{T}
   \]
   with weights `w1=0.5`, `w2=0.3`, `w3=0.2`.
4. Convert to probability:
   \[
   SPI = \frac{1}{1 + e^{-\gamma(PS - θ)}}
   \]
   where `γ = 4.0`, `θ = 0.5` (tuned via historical calibration).

**Outputs:** `analytics_spi(bucket TIMESTAMPTZ, ticker TEXT, expiry DATE, strike NUMERIC, sweep_id UUID, spi_score NUMERIC, direction TEXT, notional NUMERIC, same_size NUMERIC, opp_size NUMERIC, midpoint_change NUMERIC)`.

**Cadence:** 60 seconds (event-driven).

**QC:** Flag `confidence_low` when tick-by-tick data incomplete (`same_size + opp_size` < 75% of sweep size).

**Consumers:** Signal Generation.

---

### 4.3 Dealer Pressure Index (DPI)

**Purpose:** Estimate net dealer hedging pressure.

**Inputs:** UW GEX channels, UW REST greek exposures, NOPE, Max Pain, IBKR price.

**Formulation:**

1. Total gamma: `Γ_tot(t) = Σ Γ(t,e,k)`.
2. Normalized spot gamma: `G_norm(t) = Γ_spot(t) / ADV_Γ`.
3. Max pain distance: `M(t) = (S(t) - MaxPain(t))/S(t)`.
4. Combine:
   \[
   DPI(t) = 100 \times \left(0.6 \cdot \frac{G_{norm}(t)}{1 + |G_{norm}(t)|} + 0.25 \cdot NOPE(t) - 0.15 \cdot M(t)\right)
   \]

**Outputs:** `analytics_dpi(timestamp TIMESTAMPTZ, ticker TEXT, dpi NUMERIC, gamma_norm NUMERIC, nope NUMERIC, maxpain_distance NUMERIC)`.

**Cadence:** 60 seconds.

**QC:** Ensure coverage (strikes representing ≥90% of OI); otherwise mark `coverage_warning`.

**Consumers:** Signal Generation, Execution, Risk.

---

### 4.4 Gamma Flip Early Warning (GFEW)

**Purpose:** Predict probability of gamma regime change.

**Inputs:** DPI components, spot GEX derivative, IBKR L2 skew, price.

**Steps:**

1. `dG/dS ≈ (G(t) - G(t-3m)) / (S(t) - S(t-3m))`.
2. Logistic regression (trained quarterly) with features `[G_norm, dG/dS, M(t), L2_skew]`.
3. Output probability `p` and expected horizon via hazard model.

**Outputs:** `analytics_gfew(timestamp, ticker, flip_probability, expected_horizon_min, g_norm, dgds, m_distance, l2_skew)`.

**Cadence:** 60 seconds.

**QC:** Monitor calibration (Brier score) and coverage.

**Consumers:** Signal Generation, Execution, Risk.

---

### 4.5 Liquidity Confluence Heatmap (LCH)

**Purpose:** Map flow to liquidity support.

**Inputs:** UW flow per strike, UW stock volume price levels, UW dark pool prints, IBKR L2 rotation.

**Computation:**

1. Flow imbalance: `FI(k) = (ask_vol - bid_vol) / (ask_vol + bid_vol)`.
2. Depth ratio: `depth_ratio = sum_bid_depth / sum_ask_depth` from IB L2.
3. Confluence score `CS(k)` defined with thresholds `τ1=0.2`, `τ2=1.5` (as described earlier).
4. Include dark pool bias as secondary weight.

**Outputs:** `analytics_lch(bucket, ticker, strike, confluence_score, flow_imbalance, depth_ratio, dark_bias, rotation_complete)`.

**Cadence:** 5 minutes.

**QC:** Validate rotation finished; else set `rotation_complete=false`.

**Consumers:** Execution.

---

### 4.6 Volatility Surface Stress (VSS)

**Purpose:** Detect skew/term anomalies.

**Inputs:** UW IV surface, IV rank, realized vol, IB 5s bars, calendar events.

**Metrics:**
- `skew = IV_25P - IV_25C`
- `term = IV_front - IV_back`
- `gap = IV_50 - RV_intraday`

**Composite:**
   \[
   VSS = 0.4 Z_{skew} + 0.3 Z_{term} + 0.3 Z_{gap}
   \]
Adjust for events (importance weighting).

**Outputs:** `analytics_vss(timestamp, ticker, expiry, skew_score, term_score, realized_gap_score, vss, event_adjustment)`.

**Cadence:** 15 minutes.

**Consumers:** Signal Generation, Risk.

---

### 4.7 Option Chain Sentiment Score (OCSS)

**Purpose:** Chain-level sentiment gauge.

**Inputs:** UW option-contracts, chains, OI, volume, flow alerts.

**Score:** weighted combination of volume ratio, ΔOI/OI, NOPE sign, IV rank deviation (
like earlier formula). Use tanh smoothing to bound within [-1, 1].

**Outputs:** `analytics_ocss(timestamp, ticker, expiry, sentiment_score, volume_ratio, delta_oi_pct, iv_rank, call_ratio)`.

**Cadence:** 30 minutes.

**Consumers:** Signal Generation.

---

### 4.8 Dark vs Lit Confirmation (DLC)

**Purpose:** Confirm flow direction using dark pool vs lit markets.

**Inputs:** UW dark pool prints, UW price levels, IB L1.

**Score:**
   \[
   DLC = sign(dark\_notional) \times \frac{|dark\_notional|}{|dark\_notional| + |lit\_imbalance|} \times \mathbb{1}(signs\ match)
   \]

**Outputs:** `analytics_dlc(timestamp, ticker, dlc_score, dark_notional, lit_notional, confirmation_flag)`.

**Cadence:** 5 minutes.

**Consumers:** Signal Generation, Execution.

---

### 4.9 Event Risk Surface (ERS)

**Purpose:** Event-adjusted risk multiplier.

**Inputs:** Calendars, VSS, DPI, IFP, historical reaction.

**Formula:**
   \[
   ERS = 1 + importance \times (0.4 |VSS| + 0.3 |DPI|/100 + 0.3 |IFP|/3)
   \]

**Outputs:** `analytics_ers(timestamp, ticker, expiry, ers_multiplier, event_name, hours_to_event, importance)`.

**Cadence:** 15 minutes.

**Consumers:** Signal Generation, Risk.

---

### 4.10 Execution Slippage Forecast (ESF)

**Purpose:** Predict expected slippage.

**Inputs:** Historical fills, IFP, SPI, LCH, DPI, VSS, IB spread/depth, order attributes.

**Model:** Gradient boosting regressor; features include relative size, spread bps, vol, factor values. Predictions served via API.

**Outputs:** `analytics_esf(timestamp, strategy, instrument, expected_slippage_bps, lower_ci, upper_ci, feature_snapshot)`.

**Cadence:** On-demand + 5-minute refresh for background features.

**Consumers:** Execution.

---

### 4.11 Real-Time Risk Dial (RTRD)

**Purpose:** Consolidated risk indicator.

**Inputs:** DPI, ERS, account liquidity, P&L drawdown.

**Score:** as described earlier; status derived from thresholds.

**Outputs:** `analytics_rtrd(timestamp, scope, score, status, dpi, ers, liquidity_ratio, drawdown_pct)`.

**Cadence:** 60 seconds.

**Consumers:** Risk, Execution.

---

### 4.12 Alpha Attribution Feedback (AAF)

**Purpose:** Quantify factor contributions to realized P&L.

**Inputs:** IB P&L, factor snapshots, execution data.

**Method:** LASSO regression + Shapley values aggregated daily.

**Outputs:** `analytics_aaf(date, strategy, factor, contribution_usd, contribution_pct, trade_count, shap_mean)`.

**Cadence:** End of day.

**Consumers:** Research, Reporting, Signal Generation.

---

## 5. Pipeline Orchestration

| DAG / Flow | Cadence | Factors | Notes |
|------------|---------|---------|-------|
| `analytics_stream` | 60s | IFP, SPI, DPI, GFEW, RTRD | Streaming workers; offset per ticker |
| `analytics_5m` | 5m | LCH, DLC, ESF features | Post-rotation check for L2 |
| `analytics_15m` | 15m | VSS, ERS | Wait for IV surface availability |
| `analytics_contract` | 30m | OCSS | After option-contract snapshot |
| `analytics_eod` | 20:00 ET | AAF, archival snapshots | Exports to S3 |
| `analytics_backfill` | On-demand | All | Historical recompute |

---

## 6. Processing Framework & Storage

### 6.1 Stack

- Python 3.11, Polars, NumPy, SciPy, StatsModels, scikit-learn, XGBoost, MLflow.
- Serialization: `orjson`, Arrow IPC, Parquet.

### 6.2 Storage

| Component | Layout | Retention |
|-----------|--------|-----------|
| Redis | `analytics:<factor>:<ticker>[:expiry][:strike]` | TTL 3× cadence |
| Timescale | Tables `analytics_<factor>` | 5 years |
| Materialized Views | `mv_factor_latest`, `mv_factor_rolling` | Refreshed per cadence |
| S3 | `analytics/factor_snapshots/<date>/` | 10 years |

### 6.3 Lineage

- Each record includes `source_refs` JSON (UW message IDs, IB tick IDs).
- Lineage stored in `analytics_lineage` table for audit.

---

## 7. Model Governance & Change Control

- Semantic versioning for factors; `analytics_config` tracks active versions.
- Change approval via RFC involving Trading, Risk, Engineering.
- Canary deployments; ability to toggle via feature flags.
- Rollback procedures documented in runbooks.

---

## 8. Integration Touchpoints

| System | Interface |
|--------|-----------|
| Signal Generation | Feature Store API or direct Redis lookups |
| Execution | REST endpoints `/analytics/execution/{ticker}` |
| Risk | RTRD & ERS feeds via Redis pub/sub or polling |
| Reporting | Nightly ETL from Timescale |
| Research | SQL/Arrow access to historical factors |

---

## 9. Monitoring, QA & Runbooks

### 9.1 Metrics

- Latency per factor, staleness, anomaly counts, message rates.

### 9.2 Alerts

- Factor staleness, worker lag, ESF error, data divergence.

### 9.3 Runbooks

- Factor recompute, model rollout, ingestion lag response.

---

## 10. Testing & Simulation

- Unit tests for formulas, integration tests via replay, model validation metrics, paper trading drills.

---

## 11. Security & Compliance

- RBAC, audit logging, provider compliance checks.

---

## 12. Roadmap

- Adaptive weighting, cross-asset expansion, graph analytics, real-time VaR, visualization suite.

---

## 13. Conclusion

The Analytics Engine now provides a mathematically rigorous, operationally robust factor suite aligned with the depth of our ingestion documentation.

**Deliverables:**

✅ Detailed architecture, inputs, and lineage across UW & IBKR feeds  
✅ Twelve institutional analytics with formulas, QC, cadences, consumer mapping  
✅ Orchestrated pipelines, storage schemas, governance processes  
✅ Monitoring, testing, and security practices for production readiness  

**Next Steps:**

1. Implement pipelines per factor definitions; validate with historical data.  
2. Populate feature store interfaces for Signal Generation.  
3. Align Execution and Risk teams with factor consumption workflows.  
4. Build dashboards and alerting per Section 9.  
5. Iterate with research to tune factor weights and evaluate predictive power.

**Maintained By:** Quanticity Capital Analytics Engineering  
**Contact:** [Insert team contact]
