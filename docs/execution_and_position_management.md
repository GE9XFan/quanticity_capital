---
title: Execution & Position Management
description: Signal handoff, intelligent order routing, and position lifecycle controls integrated with Interactive Brokers.
version: 1.0.0
last_updated: 2025-10-02
---

# Execution & Position Management
## Strategy-Aware Routing and Lifecycle Control

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture & Data Flow](#2-architecture--data-flow)
3. [Client ID Coordination](#3-client-id-coordination)
4. [Signal Handoff & Intent Modeling](#4-signal-handoff--intent-modeling)
5. [Order Lifecycle](#5-order-lifecycle)
6. [Routing Strategies & Child Orders](#6-routing-strategies--child-orders)
7. [Fill Processing & Reconciliation](#7-fill-processing--reconciliation)
8. [Position Lifecycle Management](#8-position-lifecycle-management)
9. [P\&L Monitoring & Attribution](#9-pl-monitoring--attribution)
10. [Risk Safeguards & Circuit Breakers](#10-risk-safeguards--circuit-breakers)
11. [Integration Touchpoints](#11-integration-touchpoints)
12. [Monitoring & Operations](#12-monitoring--operations)
13. [Testing & Simulation](#13-testing--simulation)
14. [Conclusion](#14-conclusion)

---

## 1. Overview

### 1.1 Purpose

This document defines the **execution and position management blueprint** that transforms trading signals into actionable orders, supervises open positions, and provides real-time telemetry to risk and reporting systems.

### 1.2 Objectives

- **Deterministic signal execution**: translate analytics outputs into consistent order instructions.
- **Strategy-aware routing**: support directional, spread, and volatility strategies across SPY, QQQ, IWM, and Mag 7 options/equities.
- **Lifecycle oversight**: monitor fills, manage partial executions, and close positions according to playbooks.
- **Feedback loops**: publish performance and slippage metrics back to research, risk, and reporting.

### 1.3 Scope

- Covers production workflows interfacing with the official Interactive Brokers API (see `docs/interactive_brokers.md`).
- Excludes signal generation (see `docs/signal_generation.md`) and core risk frameworks (see `docs/risk_management.md`).

---

## 2. Architecture & Data Flow

```
┌──────────────────────────────┐
│ Signal Generation Pipeline   │
│ - UW REST/WS features        │
│ - Internal alpha models      │
└─────────────┬────────────────┘
              │ Intent payload (Target, urgency, constraints)
              ▼
┌──────────────────────────────┐
│ Execution Orchestrator       │
│ - Strategy templates         │
│ - Risk gates                 │
│ - Child order engine         │
└─────────────┬────────────────┘
              │ Orders / Modifications
              ▼
┌──────────────────────────────┐
│ IBKR Adapter (`EClient`)     │
│ - Client ID 1 (primary)      │
│ - Order primitives           │
└─────────────┬────────────────┘
              │ Fills / P&L / Positions
              ▼
┌──────────────────────────────┐
│ Execution Ledger             │
│ - Redis hot cache            │
│ - TimescaleDB history        │
└─────────────┬────────────────┘
              │
├─────────────▼──────────────┐
│ Risk Engine (Client ID 2)  │
│ - Exposure checks          │
└────────────────────────────┘
              │
              ▼
┌──────────────────────────────┐
│ Reporting & Analytics        │
│ - P&L attribution            │
│ - Compliance export          │
└──────────────────────────────┘
```

### 2.1 Services & Components

| Component | Description | Technology |
|-----------|-------------|------------|
| Execution Orchestrator | Receives trade intents, computes order schedules, enforces playbooks | Python 3.11 service (asyncio) |
| IBKR Adapter | Official API bridge (see IB doc) | `ibapi` | 
| Execution Ledger | Persists orders, fills, state machines | Redis + TimescaleDB |
| Risk Engine | Performs pre-trade/post-trade checks | Rust/Python microservice |
| Dashboard | Real-time visualization | Grafana/Influx panels |

---

## 3. Client ID Coordination

Client ID usage mirrors governance in `docs/interactive_brokers.md`.

| Component | Client ID | Function |
|-----------|-----------|----------|
| Execution Orchestrator | **1** | Places/updates/cancels orders, receives fills |
| Risk Engine (shadow polling) | 2 | Account summary, margin checks |
| Backtest / Replay | 3 | Off-market analytics (paper account) |

**Rules:**

1. Before handshake, orchestrator calls `reqCurrentTime()` with client ID 1 to verify availability.
2. On collision (`errorCode=103`), orchestrator halts and alerts operations; no orders are sent until resolved.
3. Execution ledger records client ID per order for audit.
4. Risk Management doc references same IDs when describing account/P&L subscriptions.

---

## 4. Signal Handoff & Intent Modeling

### 4.1 Intent Payload Schema

Signals arrive via Redis Stream `signals.exec.intent` (or equivalent in-memory queue) with schema:

| Field | Description |
|-------|-------------|
| `signal_id` | Unique identifier referencing analytics output |
| `strategy` | Enum (`0DTE_Scalp`, `Spread_Roll`, `Momentum_EQ`, etc.) |
| `instrument` | OCC symbol (options) or ticker symbol (equities) |
| `side` | `BUY` / `SELL` / `BUY_TO_COVER` / `SELL_SHORT` |
| `quantity` | Contracts or shares |
| `urgency` | Enum (`Immediate`, `High`, `Normal`, `Passive`) |
| `time_in_force` | `DAY`, `GTC`, `IOC`, etc. |
| `max_slippage_bps` | Maximum permitted relative slippage |
| `target_price` | Optional reference price |
| `expiry_policy` | e.g., close before market close |
| `risk_tags` | Flags (earnings, macro event, hedged) |

### 4.2 Pre-Trade Validation

- Validate instrument exists in contract cache (Section 5).
- Query Risk Engine for exposure headroom (account margin, per-instrument limits).
- Check concurrency guard: limit to N active intents per strategy to avoid overload.
- If validation fails, emit `signals.exec.reject` event with reason.

### 4.3 Intent-to-Playbook Mapping

| Strategy | Playbook | Notes |
|----------|----------|-------|
| `0DTE_Scalp` | Aggressive entry, scaling exit, mandatory flat by 15:55 ET | Focus on SPY/QQQ options |
| `Spread_Roll` | Multi-leg order via combination ID, maintain delta neutral | Uses bracket orders |
| `Momentum_EQ` | Equity smart-routing with trailing stop | Works on Mag 7 equities |
| `Gamma_Rebalance` | Hedge increments tied to spot GEX levels | Drives partial fills |

Each playbook defines order templates, risk checks, and monitoring rules.

---

## 5. Order Lifecycle

### 5.1 State Machine

```
Intent → VALIDATED → SCHEDULED → (PLACED → PARTIAL_FILLED → FILLED) → CLOSED
                             ↘ (PLACED → REJECTED)
                             ↘ (CANCEL_REQUESTED → CANCELLED)
```

- **PLACED**: Order submitted via `placeOrder` with unique ID.
- **PARTIAL_FILLED**: Execution updates increment fill quantity.
- **FILLED**: Target quantity reached; playbook triggers post-trade actions.
- **CANCELLED**: Cancel acknowledged.
- **REJECTED**: IBKR error codes 200+ or risk rejection.

State stored in `execution_orders` table (Timescale) and mirrored in Redis for dashboards.

### 5.2 Order ID Management

- Acquire next order ID via `reqIds(-1)` at session start.
- Maintain atomic counter in Redis (`ib:order:last_id`).
- On reconnect, request new base ID and ensure it is greater than stored ID.

### 5.3 Modifications & Replacements

- Modifying order reuses same `orderId` per IB guidance.
- If structural change required (e.g., from limit to bracket), cancel existing order and place new with new ID; link to original via `parent_order_id` field.

### 5.4 Cancel Policies

- IOC orders auto-cancel if not filled; system confirms via `orderStatus` events.
- Manual overrides trigger `cancelOrder` with audit log entry.
- Global kill switch uses `reqGlobalCancel()` (client ID 99 in emergencies).

---

## 6. Routing Strategies & Child Orders

### 6.1 Venue Selection

- IBKR SMART routing used by default for equities and single-leg options.
- Exchange routing (e.g., `BOX`, `CBOE`) chosen when liquidity signal indicates deeper book; configuration stored per strategy.

### 6.2 Child Order Templates

| Template | Description | Use Case |
|----------|-------------|----------|
| **Sweep** | Multiple child orders across venues with increasing aggressiveness | Urgent fills for 0DTE scalps |
| **TWAP** | Time-sliced child orders at fixed intervals | Low urgency, large size |
| **Pegged Mid** | Order pegged to midpoint with adjustable offset | Reduce slippage in balanced markets |
| **Bracket** | Parent order with stop-loss and profit-taker children | Spread rolls, equity trades |

### 6.3 Scheduling Engine

- Configurable cadence (e.g., TWAP interval 15s) implemented via asyncio tasks.
- Real-time adjustments based on incoming tick-by-tick data (e.g., widen midpoint when spread widens).
- L2 rotation data from IB (Section 4.4 IB doc) influences child placement priority.

### 6.4 Multi-Leg Orders

- Use `ComboLeg` constructs for options spreads; validate margin impact via risk engine before submission.
- Execute as single order when possible; fallback to legged execution with hedging logic.

### 6.5 Slippage Control

- Track `executed_price` vs `reference_price` at time of order.
- Abort or switch strategy if slippage exceeds `max_slippage_bps` threshold.

---

## 7. Fill Processing & Reconciliation

### 7.1 Callbacks

- `openOrder` → register working orders.
- `orderStatus` → update state (Submitted, Filled, Cancelled, etc.).
- `execDetails` → primary fill information (execution ID, price, qty, commission).
- `commissionReport` → fees & exchange info.

### 7.2 Ledger Updates

- Each execution appended to `fills` table with keys `(execution_id, order_id, conid, timestamp)`.
- Calculate cumulative quantity per order; mark order filled when total matches target.
- Commission data appended once `commissionReport` received; fallback to estimated fees if delayed.

### 7.3 Reconciliation Loop

1. Real-time: update Redis (`exec:order:{order_id}`) for dashboards.
2. Post-trade (every 5 min): reconcile totals against `reqExecutions` snapshot to detect missed events.
3. End-of-day: cross-check positions via `reqPositions` vs internal holdings; discrepancies flagged to Ops.

### 7.4 Slippage & Benchmarking

- Compute `implementation_shortfall` vs signal target price.
- Store metrics in `execution_metrics` table; feed into reporting & model retraining.

---

## 8. Position Lifecycle Management

### 8.1 Position States

| State | Description |
|-------|-------------|
| `OPEN` | Active position tracked in ledger |
| `PARTIAL` | Only fraction filled; waiting for completion |
| `HEDGED` | Offsetting leg applied to reduce net exposure |
| `CLOSING` | Exit orders in progress |
| `CLOSED` | Fully exited; awaiting final reconciliation |

### 8.2 Lifecycle Events

- **Entry**: On first fill, create position record with strategy context.
- **Scale-in/out**: Playbooks define scaling thresholds (e.g., add 25% size if price moves in favor by X).
- **Stop/Target**: Monitored via market data; triggers auto exit orders.
- **Expiry Handling**: For options, automatically close 0DTE positions by 15:55 ET unless flagged as hold-to-expiry.

### 8.3 Position Ledger

- `positions_current` table keyed by `(conid, strategy_id)` with fields: `quantity`, `avg_price`, `unrealized_pl`, `risk_tags`.
- Historical updates stored in `positions_history` for audit.

### 8.4 Portfolio Netting

- Summarize per underlying (`net_delta`, `net_gamma`) for hedging decisions.
- Publish aggregated exposures to Risk Engine every minute.

---

## 9. P&L Monitoring & Attribution

### 9.1 Data Sources

- IBKR P&L per position (`reqPnLSingle`) and per account (`reqPnL`) (see IB doc Section 6).
- Internal realized/unrealized calculations from fills and market data.

### 9.2 Real-Time Dashboard

- Redis keys: `pl:position:{conid}`, `pl:strategy:{strategy}` updated every 5 seconds.
- Grafana displays realized vs unrealized P&L, grouped by strategy and account.

### 9.3 Attribution Pipeline

1. On fill, compute incremental P&L (price vs average cost).
2. Combine with IB `pnlSingle` for validation; discrepancies > $10 flagged for manual review.
3. End-of-day attribution: allocate contributions to signals (`signal_id`) for research feedback.

### 9.4 Fees & Financing

- Commission data from IB `commissionReport` stored per execution.
- Borrow fees (for shorts) ingested nightly via IB statements; linked to positions in `financing_charges` table.

### 9.5 Reporting Handoff

- Provide CSV/Parquet extracts to reporting system with columns: `strategy`, `signal_id`, `realized_pl`, `unrealized_pl`, `fees`, `net_pl`.

---

## 10. Risk Safeguards & Circuit Breakers

### 10.1 Pre-Trade Checks

- Max order notional per instrument.
- Daily volume participation cap (e.g., 10% of 5s bar volume).
- Market status (via IB `market_data_type` + UW `stock-state`).

### 10.2 Post-Trade Monitoring

- Position limits per strategy (quantity, delta, gamma).
- Drawdown threshold: if strategy net P&L < -$X intraday, halt new orders and notify Risk.

### 10.3 Circuit Breakers

- Global kill switch triggered by risk engine or manual Ops command.
- Exchange halts detection via IB errors (e.g., `errorCode=2103`) → freeze orders in instrument.

### 10.4 Collaboration with Risk Document

- Risk Management doc details policy thresholds and escalation paths; this doc references enforcement mechanisms.

---

## 11. Integration Touchpoints

| Document | Interaction |
|----------|-------------|
| `docs/interactive_brokers.md` | Provides order primitives, client ID governance, market data feeds. Execution orchestrator relies on IB adapter service described there. |
| `docs/risk_management.md` | Supplies exposure limits, margin monitoring, and kill switch procedures. Execution publishes positions and consumes risk approvals. |
| `docs/unusual_whales_rest_api.md` & `docs/unusual_whales_websockets.md` | Provide analytics inputs and context (net premium, spot GEX) shaping routing strategies. |
| `docs/postgres_timescale.md` | Defines persistence schemas for orders, fills, positions, and metrics. |
| `docs/reporting.md` | Consumes execution ledger and attribution data. |

---

## 12. Monitoring & Operations

### 12.1 Metrics

- `exec_orders_active_total` (gauge by strategy).
- `exec_fill_latency_ms` (histogram: signal time → first fill).
- `exec_slippage_bps` (histogram by strategy).
- `exec_positions_open` (gauge by security).
- `exec_pnl_unrealized` (gauge by strategy).
- `exec_child_orders_in_flight` (gauge) to monitor TWAP/Sweep pipelines.

### 12.2 Logging & Audit

- Structured logs: `{"event": "order_submit", "order_id": 12345, "strategy": "0DTE_Scalp", "client_id": 1, "payload": {...}}`.
- Audit snapshots persisted to S3: intent, final fills, risk approvals.
- Daily reconciliation report auto-generated at 17:00 ET.

### 12.3 Alerting

- Unfilled urgent order > 2 minutes → warning.
- Slippage > threshold → notify strategy owner.
- Position discrepancy vs IB positions > 5 contracts → critical.
- Client ID collision or disconnect → immediate page.

### 12.4 Runbooks

- **Order Stuck**: Cancel, re-query position, re-place if necessary.
- **Gateway Reconnect**: Pause strategies, await IB adapter confirmation, replay pending intents.
- **Market Depth Failure**: Switch to top-of-book fallback; adjust child order aggressiveness.

---

## 13. Testing & Simulation

### 13.1 Unit & Integration Tests

- Mock `ibapi` callbacks using official sample stubs.
- Validate state machine transitions, TWAP scheduling, and reconciliation logic.

### 13.2 Paper Trading Drills

- Nightly regression in IB paper account using recorded signals.
- Validate fills vs expected, ensure P&L updates align with paper account.

### 13.3 Stress Tests

- Simulate burst of signals (e.g., 50 intents in 5 minutes) to confirm throttling & risk gates.
- Replay high-volatility sessions (FOMC) to verify circuit breakers.

### 13.4 Backtesting Interface

- Execution replay service (client ID 3) rehydrates historical market data and fills to evaluate alternative strategies without sending live orders.

---

## 14. Conclusion

Execution & Position Management binds trading intent to market reality, leveraging Interactive Brokers’ official API while enforcing risk-aware control loops.

**Key capabilities delivered:**

✅ Structured signal handoff with playbooks and risk pre-checks  
✅ Rich order lifecycle management integrated with IBKR primitives and client ID governance  
✅ Advanced routing (TWAP, sweep, bracket) and L2-informed scheduling  
✅ Comprehensive fill reconciliation, position tracking, and P&L attribution  
✅ Monitoring, alerting, and testing frameworks suitable for institutional oversight  

**Next Steps:**

1. Implement orchestrator modules per playbook and integrate with IB adapter.  
2. Align risk thresholds with `docs/risk_management.md` and configure alerting.  
3. Develop Grafana dashboards for metrics listed in Section 12.  
4. Execute paper trading drills to validate end-to-end workflow before production rollout.  
5. Schedule quarterly reviews of execution performance (slippage, fill rates) to refine strategies.

**Maintained By:** Quanticity Capital Engineering Team  
**Contact:** [Insert team contact]
