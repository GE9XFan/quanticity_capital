---
title: Risk Management
description: Capital protection guardrails, account oversight, and supervisory processes aligned with Interactive Brokers and Quanticity execution.
version: 1.0.0
last_updated: 2025-10-02
---

# Risk Management
## Multi-Layer Exposure Controls, Monitoring, and Escalation

---

## Table of Contents

1. [Risk Mandate](#1-risk-mandate)
2. [Architecture & Data Sources](#2-architecture--data-sources)
3. [Client ID Coordination](#3-client-id-coordination)
4. [Account Surveillance](#4-account-surveillance)
5. [Exposure Limits](#5-exposure-limits)
6. [Margin & Liquidity Monitoring](#6-margin--liquidity-monitoring)
7. [Real-Time Controls](#7-real-time-controls)
8. [Kill Switches & Emergency Procedures](#8-kill-switches--emergency-procedures)
9. [Stress Testing & Scenario Analysis](#9-stress-testing--scenario-analysis)
10. [Alerting & Escalation](#10-alerting--escalation)
11. [Reporting & Audit](#11-reporting--audit)
12. [Integration Touchpoints](#12-integration-touchpoints)
13. [Governance & Review Cadence](#13-governance--review-cadence)
14. [Future Enhancements](#14-future-enhancements)
15. [Conclusion](#15-conclusion)

---

## 1. Risk Mandate

### 1.1 Objective

Protect Quanticity Capital’s assets by:

- Enforcing capital, margin, and exposure limits across all strategies.
- Monitoring Interactive Brokers account telemetry in real time.
- Providing automated and manual intervention mechanisms (alerts, kill switches).
- Satisfying regulatory, compliance, and audit requirements.

### 1.2 Scope

- Applies to all trading activities routed via Interactive Brokers (equities, ETFs, listed options) and future brokers.
- Covers intraday, overnight, and event-driven risk control.
- Interfaces directly with Execution & Position Management, Signal Generation, and Reporting systems.

### 1.3 Risk Categories

| Category | Description | Owner |
|----------|-------------|-------|
| Market Risk | Directional exposure, delta/gamma, volatility | Trading + Risk |
| Liquidity Risk | Ability to exit positions under stress | Trading |
| Operational Risk | System failures, client ID conflicts | Engineering |
| Counterparty Risk | Broker solvency, data feeds | Operations |
| Compliance Risk | Regulatory reporting, market access | Compliance |

---

## 2. Architecture & Data Sources

```
┌──────────────────────────────┐
│ Interactive Brokers (IBKR)   │
│ - Account summary (Client ID 2)
│ - Positions & P&L           │
└────────────┬─────────────────┘
             │
             ▼
┌──────────────────────────────┐
│ Risk Ingestion Service       │
│ - ibapi client (read-only)   │
│ - Redis hot cache            │
│ - TimescaleDB persistence    │
└────────────┬─────────────────┘
             │
┌────────────▼──────────────┐
│ Risk Engine Core          │
│ - Exposure limits         │
│ - Margin calculators      │
│ - Alerting logic          │
└────────────┬──────────────┘
             │
┌────────────▼──────────────┐
│ Execution Orchestrator    │
│ - Pre-trade approvals     │
│ - Kill switch trigger     │
└────────────┬──────────────┘
             │
┌────────────▼──────────────┐
│ Reporting & Compliance     │
│ - Daily risk reports       │
│ - Audit trail              │
└────────────────────────────┘
```

### 2.1 Data Sources

| Source | Data | Frequency |
|--------|------|-----------|
| IBKR `reqAccountSummary` | Cash, equity, margin, available funds | 60s |
| IBKR `reqPositions` | Positions per conid | 120s or on-demand |
| IBKR `reqPnL` / `reqPnLSingle` | Account & instrument P&L | Every 5 seconds |
| Execution Ledger | Orders, fills, exposures | Real time |
| UW Analytics | Net premium, GEX, volatility | 1–15m |
| Market Data | Spot prices, L1/L2 from IBKR | Real time |

### 2.2 Technologies

- Risk ingestion service: Python 3.11 using official `ibapi`.
- Risk engine: Python + Rust for heavy calculations (delta/gamma netting).
- Storage: Redis (hot), TimescaleDB (historical), S3 for archives.
- Monitoring: Prometheus, Grafana, Alertmanager.

---

## 3. Client ID Coordination

Consistent with `docs/interactive_brokers.md`:

| Component | Client ID | Notes |
|-----------|-----------|-------|
| Execution Orchestrator | 1 | Order placement |
| **Risk Ingestion Service** | **2** | Account summary, positions, P&L (read-only) |
| Analytics/Replay | 3 | Paper trading only |

- Risk service checks client ID availability before connecting. If conflict arises (`errorCode=103`), it defers and alerts Ops.
- All account data requests use Client ID 2 to prevent interference with execution flow.

---

## 4. Account Surveillance

### 4.1 Account Summary Pipeline

- Poll `reqAccountSummary` for tags: `TotalCashValue`, `NetLiquidation`, `BuyingPower`, `ExcessLiquidity`, `InitMarginReq`, `MaintMarginReq`, `AvailableFunds`.
- Publish to Redis: `risk:account:summary:{account}` TTL 90s.
- Persist to TimescaleDB `risk_account_summary` table (retention 7 years).

### 4.2 Account Health Indicators

- **Liquidity Ratio** = `AvailableFunds / NetLiquidation`.
- **Margin Utilization** = `InitMarginReq / (NetLiquidation + LoanValue)`.
- **Cash Buffer** = `TotalCashValue - RequiredCashBuffer` (configurable).

Threshold breaches trigger alerts (Section 10).

### 4.3 Multi-Account Support

- Architecture supports multiple IB accounts; `reqAccountSummary` called per account with separate IDs.
- Combined exposures aggregated across accounts for global view.

---

## 5. Exposure Limits

### 5.1 Hierarchy of Limits

| Tier | Scope | Example |
|------|-------|---------|
| Global | Firm-wide | Net delta ≤ $25M, Total risk capital ≤ $5M |
| Strategy | Per playbook (0DTE, Spread, Momentum) | Max position notional, max drawdown |
| Instrument | Per symbol | Max contracts, max gamma exposure |
| Signal | Per trade intent | Max slippage, max order size |

### 5.2 Limit Configuration

- Limits defined in YAML (`risk_limits.yml`) loaded at startup.
- Changes require approval from Risk Committee and tracked in Git for audit.

Example snippet:

```yaml
strategy_limits:
  0DTE_Scalp:
    max_notional: 1500000
    max_contracts: 800
    max_delta: 25000
instrument_limits:
  SPY:
    max_position: 1200
    max_gamma: 500000
  QQQ:
    max_position: 900
```

### 5.3 Pre-Trade Checks

- Execution orchestrator submits `risk.pretrade.check` request with prospective order details.
- Risk engine aggregates existing exposures (from positions + pending orders) and new order impact.
- Response: `APPROVED`, `SOFT_REJECT`, or `HARD_REJECT` with reason.
- Soft rejects log warning; hard rejects block order placement and notify trader.

### 5.4 Real-Time Aggregation

- Exposure recalculated on every fill using IBKR market data.
- Delta/gamma netting performed per underlying, considering option greeks from UW + IB contract snapshots.

---

## 6. Margin & Liquidity Monitoring

### 6.1 Margin Metrics

- Track `ExcessLiquidity`, `AvailableFunds`, `MaintMarginReq`.
- Compute margin buffers relative to thresholds.
- Scenario analysis (Section 9) predicts margin impact of price shocks.

### 6.2 Liquidity Stress Signals

- Monitor `VolumeParticipation` vs market volume (from UW net premium + IB bars).
- If daily participation > configured limit (e.g., 5%), risk engine throttles new orders.

### 6.3 Funding & Cash Management

- Daily reconciliation with back-office (ACH, swap financing).
- Forecast cash needs for upcoming trades; integrate with treasury planning.

---

## 7. Real-Time Controls

### 7.1 Guardrail Types

| Control | Description |
|---------|-------------|
| Pre-Trade Block | Reject orders exceeding limits or during halt events |
| Throttle | Reduce order rate when message volume or participation high |
| Auto Hedge | Trigger hedging trades when net delta/gamma crosses thresholds |
| Auto Exit | Force close positions before events (earnings, end-of-day) |
| Stop Trading | Halt new signals for strategy exceeding drawdown |

### 7.2 Event-Driven Rules

- Scheduled events (NFP, FOMC) flagged from UW calendar; risk engine elevates thresholds or restricts strategies.
- Exchange halts detected via IB errors cause immediate block on affected instruments.

### 7.3 Collaboration with Execution

- Execution doc (Section 10) describes enforcement mechanism; risk engine issues `risk.control.command` messages consumed by orchestrator.

---

## 8. Kill Switches & Emergency Procedures

### 8.1 Kill Switch Types

| Switch | Trigger | Effect |
|--------|---------|--------|
| Global | Manual Ops command or automated threshold | Calls `reqGlobalCancel`, halts new orders |
| Strategy | Strategy-specific drawdown | Blocks orders tagged with strategy |
| Instrument | Market halt or extreme volatility | Cancels open orders, prevents new ones |

### 8.2 Activation Workflow

1. Risk engine raises `kill_switch` event with context (strategy/instrument).
2. Execution orchestrator cancels relevant orders, confirms kills.
3. Risk service monitors IB confirmations (order status = Cancelled).
4. Resume requires manual override from Risk Officer with documented reason.

### 8.3 Manual Intervention

- Ops console offers buttons: `Pause Strategy`, `Resume Strategy`, `Stop All`.
- Manual actions logged with user, timestamp, reason, and affected orders.

### 8.4 Disaster Recovery

- If IB Gateway unreachable, fall back to paper gateway for monitoring while trading halted.
- Maintain out-of-band contact with IB (phone) for broker-side issues.

---

## 9. Stress Testing & Scenario Analysis

### 9.1 Intraday What-If Engine

- Simulate price shocks (±1%, ±3%) on underlying; compute impact on delta, gamma, margin.
- Evaluate worst-case net P&L given positions.

### 9.2 Scheduled Stress Runs

- Daily pre-market: evaluate major indices ±5%, volatility spike (IV +30%).
- Weekly: combined stress (earnings + macro) for top exposures.

### 9.3 Historical Replay

- Use execution replay service (client ID 3) with past data (e.g., March 2020) to evaluate control effectiveness.

### 9.4 Reporting

- Store stress results in `risk_stress_tests` table; share summaries with management.

---

## 10. Alerting & Escalation

### 10.1 Alert Framework

| Alert | Trigger | Severity |
|-------|---------|----------|
| Margin Warning | `ExcessLiquidity < Threshold1` | Warning |
| Margin Breach | `ExcessLiquidity < Threshold2` | Critical, auto kill switch |
| Limit Exceeded | Strategy/instrument limit | Critical |
| Drawdown Alert | Strategy P&L < configured limit | Warning/Critical |
| Client ID Collision | Risk service unable to connect | Critical |

Alerts sent via Slack (#risk-alerts), email, and PagerDuty depending on severity.

### 10.2 Escalation Matrix

| Severity | Action |
|----------|--------|
| Warning | Notify trading desk, track resolution |
| Critical | Auto block, notify Risk Officer, escalate to CIO |
| Emergency | Suspend trading, contact IB, inform compliance |

### 10.3 Acknowledgment & Resolution

- Alerts require acknowledgment within SLA (5 minutes for critical).
- Resolution notes recorded in risk incident log.

---

## 11. Reporting & Audit

### 11.1 Daily Risk Report

- Snapshot of exposures, margin, P&L, limits status.
- Delivered 07:30 ET to management and compliance.

### 11.2 Weekly Review

- Aggregated slippage, participation, drawdown stats.
- Review of triggered alerts and responses.

### 11.3 Regulatory Artifacts

- Maintain order audit trail, account statements, and limit change logs for regulatory inspections.
- Map to SEC/FINRA requirements as applicable.

### 11.4 Data Retention

- Account summaries, positions, P&L: retain 7 years.
- Alerts & incidents: retain 10 years.
- Stress test results: retain 5 years.

---

## 12. Integration Touchpoints

| Document | Interaction |
|----------|-------------|
| `docs/interactive_brokers.md` | Supplies account summary, positions, P&L data via Client ID 2; defines connectivity and rotation constraints relied upon by risk ingestion. |
| `docs/execution_and_position_management.md` | Risk engine authorizes orders, issues kill switches, and consumes position states; execution doc outlines enforcement mechanisms. |
| `docs/unusual_whales_rest_api.md` & `docs/unusual_whales_websockets.md` | Provide analytics (spot GEX, net premium, volatility) used in risk scenarios and guardrails. |
| `docs/reporting.md` | Uses risk reports and metrics for stakeholder communication. |
| `docs/postgres_timescale.md` | Defines schema for risk tables (account summary, stress tests, incidents). |

---

## 13. Governance & Review Cadence

### 13.1 Risk Committee

- Members: CIO, Head of Trading, Risk Officer, CTO.
- Meets weekly; reviews limit breaches, performance, upcoming events.

### 13.2 Policy Reviews

- Quarterly review of risk policies, limits, and kill switch thresholds.
- Annual comprehensive review with compliance/legal.

### 13.3 Change Management

- Any limit change requires Jira ticket, Risk Officer approval, and deployment via CI/CD.
- Emergency changes logged with post-mortem within 24 hours.

---

## 14. Future Enhancements

- Integrate machine learning anomaly detection for exposure drift.
- Expand counterparty risk monitoring (multiple brokers).
- Automate capital allocation adjustments based on volatility regimes.
- Implement real-time VaR calculation for option portfolios.
- Support multi-currency accounts and FX hedging limits.

---

## 15. Conclusion

The risk management framework enforces disciplined trading by combining IBKR-derived telemetry with internal analytics to watch exposures, margin, and P&L in real time.

**Deliverables:**

✅ Continuous account surveillance aligned with Interactive Brokers client ID governance  
✅ Hierarchical exposure limits and pre-trade/post-trade checks integrated with execution workflows  
✅ Margin, liquidity, and stress-test monitoring with automated alerting and kill switches  
✅ Comprehensive reporting, audit trails, and governance processes  

**Next Steps:**

1. Implement risk ingestion service using official IB API; verify client ID coordination.  
2. Configure limits and thresholds in `risk_limits.yml`; test pre-trade checks with execution orchestrator.  
3. Build dashboards and alerting for account health, exposures, and kill switches.  
4. Schedule initial risk committee review and document baseline metrics.  
5. Plan for future enhancements (VaR, anomaly detection) once baseline is operational.

**Maintained By:** Quanticity Capital Risk & Engineering Teams  
**Contact:** [Insert team contact]
