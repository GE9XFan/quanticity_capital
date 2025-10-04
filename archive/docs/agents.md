# System Agents Overview

This document tracks the primary agents/services in the automated options trading platform. It will evolve as each phase is delivered. Keep documentation synchronized with any code or configuration changes that affect an agent's responsibilities, inputs, outputs, or operational playbook.

## Documentation Expectations
- Update this file whenever an agent gains or loses a responsibility, data contract, or dependency.
- Cross-link to deeper design or runbook docs as they appear (e.g., Phase-specific guides, API specs, dashboard manuals).
- Note any manual procedures, external approvals, or credentials the agent requires.

## Agents (Initial Draft)

> **Phase 0 status:** Repository scaffolding, FastAPI skeleton, Docker/compose stack, smoke tests, and runtime version documentation (`docs/runtime_environment.md`, `docs/runtime_versions.txt`) are complete. Implementation details below note pending work per phase.

### 1. Ingestion Service
- **Scope:** Connects to Unusual Whales REST/WebSocket feeds (Phase 1) and, later, Interactive Brokers market data (Phase 2+).
- **Responsibilities (current):**
  - Maintain Unusual Whales WebSocket subscriptions (flow alerts, price, option trades, GEX, news), normalize payloads, and push to Redis/Postgres.
  - Schedule confirmed Unusual Whales REST endpoints, archive raw JSON responses (`uw_rest_payloads`), and manage request cadences.
  - Track raw payload fixtures/tests for drift detection; surface ingestion metrics (pending).
- **Deferred Responsibilities:** IB market data ingestion and TWS restart handling arrive in Phase 2.
- **Key Data Touchpoints:**
  - Redis keys: `uw:flow_alerts`, `latest:uw:*`, `uw:price_ticks:*`, etc.
  - Postgres tables: `uw_flow_alerts`, `uw_option_trades`, `uw_gex_*`, `uw_price_ticks`, `uw_news`, `uw_rest_payloads`.
- **Phase Notes:** Phase 1 implementation complete for Unusual Whales; IB adapters remain TODO in Phase 2.

### 2. Analytics Workers
- **Scope:** Transform raw ingestion data into enriched analytics and forward predictions.
- **Responsibilities:**
  - Subscribe to ingestion streams, compute derived metrics per strategy bucket.
  - Store analytics snapshots in Redis Hashes and archive to Postgres where historical view is needed.
  - Emit structured events (JSON with schema version, features used, confidence scores).
- **Key Data Touchpoints:**
  - Redis keys: `analytics:*`, `predictions:*`.
  - Postgres tables: future `analytics_*` tables (to be defined in Phase 3).
- **Phase Notes:** To be implemented after ingestion pipeline stabilizes (Phase 3).

### 3. Signal Engine
- **Scope:** Generate trade signals for 0DTE, 1DTE, 14D+, and MOC strategies across SPY/QQQ/IWM.
- **Responsibilities:**
  - Consume analytics outputs and risk constraints to produce actionable signals.
  - Attach explainability metadata (feature contributions, rationale, version tags).
  - Persist signal state in Redis for real-time access and Postgres for audit.
- **Key Data Touchpoints:**
  - Redis keys: `signals:pending`, `signals:active`.
  - Postgres tables: `signals` (schema to be defined in Phase 4).
- **Phase Notes:** Strategy modules scheduled for Phase 4.

### 4. Risk Manager
- **Scope:** Validate signals against account balances, margin, open PnL, and risk rules.
- **Responsibilities:**
  - Pull live balances/positions from IB API on demand.
  - Calculate position sizing, leverage checks, and kill-switch conditions.
  - Approve or reject signals and record decision rationale.
- **Key Data Touchpoints:**
  - Redis keys: `risk:decisions`, `risk:limits`.
  - Postgres tables: `risk_audit` for 2-year retention.
- **Phase Notes:** Risk rule design slated for Phase 5.

### 5. Execution Engine
- **Scope:** Place and manage orders via IB, monitor fills, and adjust stops.
- **Responsibilities:**
  - Submit idempotent orders, track order lifecycle, and reconcile status with IB.
  - Publish fill updates and PnL adjustments to Redis for distribution.
  - Trigger stop/exit logic based on risk directives or profit targets.
- **Key Data Touchpoints:**
  - Redis keys: `execution:orders`, `positions:live`.
  - Postgres tables: `trades`, `trade_logs` (nightly export target).
- **Phase Notes:** Execution wiring depends on Phase 5 risk outputs.

### 6. Distribution Service
- **Scope:** Broadcast trades and updates to Discord tiers, manage social queues, and archive communications.
- **Responsibilities:**
  - Format and send Discord messages with tiered release delays (0s, +60s, +5m).
  - Queue social content (Twitter, Reddit) for Telegram approval and publish once approved.
  - Mirror all outbound content and approvals to Postgres for retention.
- **Key Data Touchpoints:**
  - Redis keys: `distribution:queue`, `distribution:scheduled`, `distribution:approvals`.
  - Postgres tables: `distribution_logs`, `social_queue`.
- **Phase Notes:** Scheduled for Phase 6 implementation.

### 7. AI Commentator / Overseer
- **Scope:** Generate market reports and trade explainability using Claude Haiku; route through Telegram approvals.
- **Responsibilities:**
  - Aggregate relevant analytics/trade context, build prompts, call Anthropic API.
  - Schedule pre-market, intraday, post-market reports via cron.
  - Provide structured explainability for executed trades.
- **Key Data Touchpoints:**
  - Redis keys: `ai:reports:pending`, `ai:explainability`.
  - Postgres tables: `ai_reports`, `ai_explainability`.
- **Phase Notes:** Planned deliverable in Phase 7.

### 8. Operations Dashboard
- **Scope:** Frontend portal for system health, controls, and audit views.
- **Responsibilities:**
  - Display live metrics (Redis memory, ingestion rates, queue backlogs, active trades).
  - Offer controls to pause feeds, flush caches, override trades, acknowledge alerts.
  - Surface recent distribution events and approval statuses.
- **Key Data Touchpoints:**
  - Reads from Redis metrics endpoints, Prometheus exporter, and Postgres summary views.
- **Phase Notes:** Dashboard build targeted for Phase 8.

### 9. Observability Layer
- **Scope:** Central logging, metrics, and alerting utilities.
- **Responsibilities:**
  - Aggregate structured logs from services.
  - Expose Prometheus metrics; maintain alert rules (Redis memory, Postgres lag, IB disconnect).
  - Integrate alerts with chosen notification channel (to be defined).
- **Key Data Touchpoints:**
  - Log storage (stdout aggregation, optional file sink).
  - Metrics exporter endpoints.
- **Phase Notes:** Baseline logging exists (FastAPI defaults); Prometheus integration to be addressed in later phases.

---

**Maintenance Note:** Revisit this document after each phase to capture new agents, responsibilities, or key data changes. Keeping it accurate ensures the implementation and operations runbooks stay aligned.
