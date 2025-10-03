---
title: Interactive Brokers Integration
description: Connectivity, data ingestion, and order primitives built on the official Interactive Brokers TWS API.
version: 1.0.0
last_updated: 2025-10-02
---

# Interactive Brokers Integration
## Official TWS API Connectivity, Market Data, and Order Foundations

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture & Connectivity](#2-architecture--connectivity)
3. [Client ID Governance](#3-client-id-governance)
4. [Market Data Subscriptions](#4-market-data-subscriptions)
5. [Contract & Symbol Management](#5-contract--symbol-management)
6. [Account, Portfolio & P\&L Feeds](#6-account-portfolio--pl-feeds)
7. [Order Management Primitives](#7-order-management-primitives)
8. [Error Handling & Recovery](#8-error-handling--recovery)
9. [Rate Limits & Throttling](#9-rate-limits--throttling)
10. [Monitoring & Operations](#10-monitoring--operations)
11. [Integration Touchpoints](#11-integration-touchpoints)
12. [Testing & Certification](#12-testing--certification)
13. [Conclusion](#13-conclusion)

---

## 1. Overview

### 1.1 Strategic Role

Interactive Brokers (IBKR) is our **execution and broker data provider**, delivering:

- **Authoritative market data** for SPY, QQQ, IWM, Mag 7, and auxiliary symbols: top-of-book L1, market depth (L2), tick-by-tick trades/quotes, and native 5-second bars.
- **Account telemetry**: account summary, portfolio positions, margin metrics, and P\&L streams that underpin risk and reporting.
- **Order routing primitives**: the canonical path for placing, modifying, and canceling orders destined for exchanges or smart routers.

We integrate exclusively with the **official IB API** as documented at <https://interactivebrokers.github.io/tws-api/>. Third-party wrappers (e.g., `ib_insync`, `ibapi-async`) are **not** used to ensure full vendor support, compatibility, and regulatory compliance.

### 1.2 Document Scope

This document covers:

1. Connectivity to Trader Workstation (TWS) or IB Gateway via the official Python API (`EClient`/`EWrapper`).
2. Market data ingestion (L1, L2, tick-by-tick, 5-second bars) with emphasis on IB’s level-2 subscription constraints.
3. Contract definition, account data flows, P\&L subscriptions, and order lifecycle primitives.
4. Error handling, rate limiting, and operational procedures.
5. Integration points with **Execution & Position Management** and **Risk Management** documents, including client ID requirements.

Downstream documents expand on trade lifecycle and risk controls; this file establishes the IBKR foundation they rely on.

---

## 2. Architecture & Connectivity

### 2.1 Reference Architecture

```
┌────────────────────────────────────────────┐
│             TWS / IB Gateway               │
│ (Primary: Chicago DC, Failover: Greenwich) │
└───────────────┬────────────────────────────┘
                │ TCP 7497/7496 (SSL)
                ▼
┌────────────────────────────────────────────┐
│    IBKR Adapter Service (Python 3.11)      │
│  - Official ibapi.EClient / ibapi.EWrapper │
│  - Dedicated network thread (reader)       │
│  - Message queue bridge (asyncio)          │
└───────────────┬─────────┬──────────────────┘
                │         │
       Market Data Bus    │ Order Routing Bus
                │         │
                ▼         ▼
   ┌────────────────┐   ┌────────────────┐
   │ Data Lakehouse │   │ Execution Eng. │
   │ (Redis/TSDB)   │   │ (see doc)      │
   └────────────────┘   └────────────────┘
                │         │
                ▼         ▼
   ┌────────────────┐   ┌────────────────┐
   │ Risk Controls  │   │ Reporting      │
   │ (limit checks) │   │ & Monitoring   │
   └────────────────┘   └────────────────┘
```

### 2.2 Session Management

- **Connectivity Mode**: IB Gateway (headless) in production, TWS in development for manual oversight.
- **Transport**: TCP with optional SSL; ports configurable (default 4002/4001 for Gateway, 7497/7496 for TWS). Firewalls allow outbound only.
- **Threading Model**: Official API requires `EClient` on main thread and `reader` thread calling `EWrapper`. Our adapter:
  - Runs `EClient.connect()` on a controller thread.
  - Spawns `Reader` thread invoking `processMessages()` per official guidance ([API Reference: Connecting to TWS](https://interactivebrokers.github.io/tws-api/connection.html)).
  - Bridges messages onto an asyncio queue for downstream consumers.
- **Heartbeat**: Monitor `connectionClosed()` callback; issue periodic `reqCurrentTime` to detect stale sessions.
- **Failover**: Secondary IB Gateway in alternate region; switch triggered after 3 failed reconnect attempts.

### 2.3 Authentication & Permissions

- API access is controlled by IBKR’s **username/password + security code** (for TWS) or **certificates** (Gateway). Credentials stored in Vault.
- Market data permissions audited to confirm Level II availability for specific exchanges (NASDAQ TotalView, NYSE OpenBook, ARCA). Only 3 simultaneous market depth subscriptions are permitted for our account.
- Compliance requires logging all connections/disconnections with timestamps.

### 2.4 Environment Separation

| Environment | Host | Client Version | Notes |
|-------------|------|----------------|-------|
| Development | Local TWS | Latest stable | Manual testing, paper trading account |
| Staging | IB Gateway (paper) | Locked to version used in prod | Integration tests, nightly rehearsals |
| Production | IB Gateway (live) | n-1 stable | HA pair; automatic restart 05:00 ET |

---

## 3. Client ID Governance

Client IDs differentiate sessions interacting with IBKR. The official API enforces single active session per client ID; collisions cause disconnections. Governance is critical across IBKR, Execution & Position Management, and Risk Management.

| Component | Client ID | Purpose | Notes |
|-----------|-----------|---------|-------|
| `ibkr_adapter` (core data + orders) | 1 | Primary market data + order routing | Must be active for all trading hours |
| `risk_manager` (account surveillance) | 2 | Account summary, margin snapshots | Read-only; no orders |
| `execution_replay` (analytics/backtest) | 3 | Non-trading analytics; can be offline | Connects to paper accounts only |
| Emergency manual console | 99 | Human intervention | Used only during incidents; requires coordination |

**Rules:**

- Client IDs defined centrally in configuration and referenced by all three documents.
- Before connecting, each component verifies availability by calling `reqCurrentTime`. If rejection occurs, component backs off and alerts Ops.
- Client ID usage logged to ensure no rogue sessions exist.
- Execution & Position Management doc references this table when describing order workflows; Risk Management doc uses same IDs for account subscriptions.

---

## 4. Market Data Subscriptions

All market data requests follow the official API methods documented at <https://interactivebrokers.github.io/tws-api/market_data.html>. We utilize only the **standard `EClient` methods**.

### 4.1 Level 1 Top-of-Book

- **Method**: `reqMktData(tickerId, Contract, genericTickList, snapshot, regulatorySnapshot, mktDataOptions)`.
- **Data Types**: `tickPrice`, `tickSize`, `tickString`, `tickGeneric`, `tickReqParams` callbacks.
- **Usage**: Provide bid/ask/last quotes with exchange codes; feed combined with UW price streams for reconciliation.
- **Tick List**: Include `233` (RTVolume), `236` (Shortable), `258` (Last Timestamp) as needed.
- **Persistence**: Published to Redis (`ib:l1:{symbol}`) with TTL 5 seconds; stored in TimescaleDB for auditing.

### 4.2 Tick-by-Tick Data

- **Method**: `reqTickByTickData(tickerId, Contract, tickType, numberOfTicks, ignoreSize)`.
- **Types**: `"Last"`, `"BidAsk"`, `"AllLast"`, `"MidPoint"`.
- **Latency**: Target < 300ms from IBKR; used for microstructure analytics and verifying UW flow events.
- **Limitations**: IB throttles to 1 concurrent request per symbol; we activate for SPY, QQQ, and rotating third ticker matching active trade scenario.

### 4.3 Real-Time Bars (5-Second)

- **Method**: `reqRealTimeBars(tickerId, Contract, barSize, whatToShow, useRTH, realTimeBarsOptions)` with `barSize=5`, `whatToShow="TRADES"`.
- **Callbacks**: `realtimeBar(tickerId, time, open, high, low, close, volume, wap, count)`.
- **Usage**: Provide continuous 5s bars aligned with internal analytics and comparison to UW minute ticks.
- **Storage**: `ib_realtime_bars_5s` Timescale hypertable with 30-day compression.

### 4.4 Market Depth (Level 2)

- **Method**: `reqMktDepthExchanges()`, `reqMktDepth(tickerId, Contract, numRows, isSmartDepth, mktDepthOptions)`.
- **Constraint**: IB permits **only three concurrent market depth subscriptions** given our permission package. **SPY must remain permanently subscribed**; the other two slots rotate.

**Rotation Strategy:**

1. Maintain priority queue of symbols needing L2 (e.g., QQQ, IWM, NVDA, TSLA, AMZN, MSFT, META, GOOG).
2. Scheduler assigns slot durations (default 10 seconds). For each cycle:
   - Subscribe to next two symbols via `reqMktDepth`.
   - Consume updates via `updateMktDepth` / `updateMktDepthL2` callbacks.
   - After duration, send `cancelMktDepth` and wait for confirmation to free slot.
   - Move symbols to queue tail.
3. SPY subscription is never canceled; tickerId reserved (e.g., 9001).
4. Publish rotation state metrics (active symbols, time remaining).

**Fallback**: If rotation fails (e.g., cancel not acknowledged), disable rotation and raise alert. Execution & Position Management doc references this mechanism when explaining order book-informed routing.

### 4.5 Market Data Unsubscription & Cleanup

- On service shutdown, **cancel all subscriptions**: `cancelMktData`, `cancelMktDepth`, `cancelRealTimeBars`, `cancelTickByTickData`.
- Implement kill switch to avoid orphan subscriptions that could exhaust allowed quota.

---

## 5. Contract & Symbol Management

### 5.1 Contract Creation

We construct official `Contract` objects per <https://interactivebrokers.github.io/tws-api/basic_contracts.html>.

- **Equities/ETFs**: `Contract.secType="STK"`, `currency="USD"`, `exchange="SMART"`, `primaryExchange="ARCA"/"NASDAQ"` as appropriate.
- **Options**: `Contract.secType="OPT"`, `right="C"/"P"`, `lastTradeDateOrContractMonth`, `strike`, `multiplier="100"`. OCC symbols sourced from UW docs.

Example:

```python
from ibapi.contract import Contract

def make_equity(symbol: str) -> Contract:
    c = Contract()
    c.symbol = symbol
    c.secType = "STK"
    c.currency = "USD"
    c.exchange = "SMART"
    c.primaryExchange = "NYSE" if symbol in {"SPY", "IWM"} else "NASDAQ"
    return c
```

### 5.2 Contract Details Workflow

- Request: `reqContractDetails(reqId, Contract)`.
- Receive: `contractDetails(reqId, ContractDetails)` repeated per exchange.
- Completion: `contractDetailsEnd(reqId)` signals ready state.
- Persist details (conid, min tick, trading class, valid exchanges) to `ib_contract_reference` table.
- This data is consumed by Execution & Position Management for order routing and by Risk Management for margin calculations.

### 5.3 Contract Validation & Mapping

- Map UW OCC symbol to IB conid; mismatch triggers warning.
- Cache contract metadata in Redis (`ib:contract:{conid}`) with TTL 24h.
- Refresh contract details daily at 07:00 ET to capture symbol changes.

---

## 6. Account, Portfolio & P&L Feeds

Reference: <https://interactivebrokers.github.io/tws-api/account_updates.html>

### 6.1 Account Summary

- Request: `reqAccountSummary(reqId, group, tags)` with `group="All"`, `tags="AccountType,TotalCashValue,NetLiquidation,BuyingPower,ExcessLiquidity,MaintMarginReq"`.
- Callbacks: `accountSummary(reqId, account, tag, value, currency)`, `accountSummaryEnd`.
- Frequency: Every 60 seconds during trading hours; additional pull on significant events (margin alert).
- Data is forwarded to Risk Management for exposure calculations.

### 6.2 Portfolio Updates

- Request: `reqPositions()` at session start; `position()` callbacks per instrument; `positionEnd()` indicates completion.
- Real-time updates: subscribe to `positionMulti` if needed for multiple accounts.
- Execution & Position Management uses this data to reconcile actual vs expected holdings.

### 6.3 P&L Subscriptions

- **Per Account**:
  - `reqPnL(reqId, account, modelCode)`.
  - Callbacks: `pnl(reqId, dailyPnL, unrealizedPnL, realizedPnL)`.
  - Cancel: `cancelPnL(reqId)` on shutdown.
- **Per Position**:
  - `reqPnLSingle(reqId, account, modelCode, conId)`.
  - Callbacks: `pnlSingle(reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value)`.
  - Cancel: `cancelPnLSingle(reqId)`.
- P&L data ensures Execution & Position Management can attribute performance per trade, while Risk Management tracks account-level health.

### 6.4 Cash Balances & Margin

- Use `accountSummary` tags: `InitMarginReq`, `MaintMarginReq`, `AvailableFunds`, `ExcessLiquidity`.
- On margin warning (e.g., `AvailableFunds < threshold`), risk engine triggers exposure reductions (see Risk doc).

### 6.5 Data Persistence

- Redis: `ib:account:summary`, `ib:positions`, `ib:pl` with TTL 120s for dashboards.
- TimescaleDB: `ib_account_summary`, `ib_positions`, `ib_pl` tables; retention 5 years for audit.

---

## 7. Order Management Primitives

Reference: <https://interactivebrokers.github.io/tws-api/order_submission.html>

### 7.1 Order Object Construction

- `Order` fields set according to execution strategy: `orderType`, `totalQuantity`, `action`, `tif`, `auxPrice`, `lmtPrice`, `transmit`.
- Example:

```python
from ibapi.order import Order

def make_limit_order(action: str, quantity: float, price: float) -> Order:
    order = Order()
    order.action = action  # "BUY" or "SELL"
    order.orderType = "LMT"
    order.totalQuantity = quantity
    order.lmtPrice = price
    order.tif = "DAY"
    order.transmit = True
    return order
```

### 7.2 Place, Modify, Cancel

- Place: `placeOrder(orderId, Contract, Order)`; response via `orderStatus`, `openOrder`, `execDetails`.
- Modify: reissue `placeOrder` with same `orderId` and updated order parameters (official guidance).
- Cancel: `cancelOrder(orderId)`; watch for `orderStatus(..., status="Cancelled")`.
- Execution details forwarded to Execution & Position Management for fill tracking.

### 7.3 Order ID Management

- Use `reqIds(-1)` to obtain next valid order ID; maintain monotonic increment per session.
- Persist last used order ID in Redis (`ib:order:last_id`) to survive reconnects.

### 7.4 Compliance & Audit

- Log every order request/response pair with timestamps, client ID, and payload snapshot.
- Provide daily audit trail to compliance share.

### 7.5 Handoff to Execution & Position Management

- This document defines primitive operations; the **Execution & Position Management** doc describes higher-level strategies (bracket orders, child slicing, smart routing) using these primitives.

---

## 8. Error Handling & Recovery

### 8.1 Error Callbacks

- `error(reqId, errorCode, errorString)` is central; refer to official error code list (<https://interactivebrokers.github.io/tws-api/message_codes.html>). Examples:
  - `1100`: Connectivity between IBKR and TWS dropped – trigger reconnect.
  - `10167`: Market data farm connection is OK – informational.
  - `321`: Server error validating request – log and escalate.

### 8.2 Reconnect Logic

1. On connection loss, stop market data rotation.
2. Attempt reconnects with exponential backoff (1s → 60s). After 3 failures, trigger failover to backup gateway.
3. Upon reconnection, re-request:
   - Contract details (if cleared),
   - Market data subscriptions (respect rotation schedule),
   - Account summary & positions,
   - P&L subscriptions.
4. Validate order ID sequence via `reqIds(-1)` before resuming trading.

### 8.3 Data Consistency Checks

- If `pendingTickers` backlog grows beyond threshold, pause new subscriptions.
- Duplicate execution IDs detected via `execDetails`; ignore duplicates but log occurrences.

### 8.4 Manual Intervention

- Provide runbook for manual disconnection from TWS GUI to free stuck client IDs.
- Emergency console (client ID 99) can cancel all orders using `reqGlobalCancel()`.

---

## 9. Rate Limits & Throttling

Reference: <https://interactivebrokers.github.io/tws-api/pace_of_operations.html>

- IBKR enforces **50 messages in any 1-second interval** and additional limits per data type.
- Adapter maintains message counter; before sending new request, ensure `messages_last_second < 45` (safety headroom).
- Market data rotation scheduler staggers subscriptions to stay within message budget.
- Historical data requests (if any) throttled to 6/min as per IB guidance.

---

## 10. Monitoring & Operations

### 10.1 Metrics

- `ib_connection_status` (gauge: 1=connected, 0=down).
- `ib_clientid_active{client_id}` (gauge) verifying no duplicates.
- `ib_mktdepth_active{symbol}` (gauge) for rotation visibility.
- `ib_message_rate_per_sec` (gauge) vs limit.
- `ib_order_error_total` (counter) by error code.

### 10.2 Logging

- Structured logs using structlog: include `event`, `reqId`, `clientId`, `symbol`, `errorCode`.
- Audit log for orders stored in append-only S3 bucket.

### 10.3 Alerting

- Reconnect failure after 3 attempts → PagerDuty incident.
- Market depth rotation stuck > 30 seconds on same symbol → warning.
- Client ID collision detection (`ERROR 102`) → critical.

### 10.4 Maintenance

- Gateway restarts daily at 04:45 ET; adapter reconnects automatically.
- Quarterly upgrade plan to align with IBKR API version support window.

### 10.5 Compliance

- Maintain records of enablement letters for market data.
- Ensure FIX/ARCA/NYSE reporting obligations met via stored execution logs.

---

## 11. Integration Touchpoints

| Document | Dependency | Interaction |
|----------|------------|-------------|
| **Execution & Position Management** | Builds on Sections 5–7 | Uses contract metadata, L1/L2 data, order primitives, P&L streams to implement strategy-specific routing and position lifecycle. References client ID table to ensure coordination. |
| **Risk Management** | Builds on Sections 3 & 6 | Consumes account summaries, positions, margin metrics, per-position P&L. Uses same client ID governance to avoid session conflicts. |
| **Signal Generation** | Consumes Section 4 | Integrates IB real-time bars and tick data with UW feeds for model inputs. |
| **Reporting** | Consumes Sections 6 & 10 | Uses account/portfolio data plus monitoring metrics for daily reports. |

Explicit cross references in those documents should cite this file for connection, client ID, and data feed details.

---

## 12. Testing & Certification

- **Sandbox Testing**: Paper trading account mirrors production instruments; run automated regression verifying:
  - Connection lifecycle,
  - L1/L2 data reception,
  - Order placement/cancel round-trip,
  - Account summary parsing.
- **Certification**: Annual compliance check ensures API usage conforms to IBKR agreements.
- **Simulation**: Off-market hours simulation using recorded ticks piped into adapter for load testing (no orders transmitted).

---

## 13. Conclusion

This Interactive Brokers integration blueprint establishes the official, supportable connection layer for Quanticity Capital’s trading stack.

**Key deliverables:**

✅ Official IB API usage with clearly defined client IDs and session discipline  
✅ Comprehensive market data ingestion (L1, tick-by-tick, 5-second bars, L2 with rotation) respecting IB constraints  
✅ Contract, account, portfolio, and P\&L workflows synchronized with downstream Execution & Risk documents  
✅ Order management primitives, error handling, and rate-limit safeguards aligned with vendor requirements  
✅ Monitoring, logging, and compliance controls supporting institutional operations  

**Next Steps:**

1. Implement adapter service using official `ibapi` package; integrate with rotation scheduler.  
2. Wire data feeds into Execution & Position Management and Risk systems, referencing client ID governance.  
3. Build alerting dashboards for connection health, market depth rotation, and message rates.  
4. Conduct end-to-end tests in paper environment, then stage to production.  
5. Schedule quarterly reviews of IB permissions and gateway versions.

**Maintained By:** Quanticity Capital Engineering Team  
**Contact:** [Insert team contact]
