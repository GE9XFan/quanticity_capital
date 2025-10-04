# Automated Options Trading Platform - Project Scope

## 1. Purpose
Establish a baseline plan for building a SPY/QQQ/IWM automated options trading platform covering ingestion, analytics, signal generation, risk, execution, distribution, AI commentary, and observability. This document captures the agreed technology choices, data architecture, workflows, testing expectations, and delivery roadmap for the solo-development effort.

## 2. Guiding Principles
- Keep the system as simple as feasible while maintaining reliability and auditability.
- Favor single-repo, modular Python code with clear boundaries between stages.
- Use Redis for hot state and inter-service messaging; persist history and logs in Postgres.
- Design for local Mac development with Dockerized services to ease later GCP deployment.
- Maintain clear manual intervention points (Telegram approvals, dashboard controls).
- Prefer real API integration tests to validate field mapping and behavior before production runs.

## 3. Target Strategies and Instruments
- Instruments: SPY, QQQ, IWM.
- Strategy buckets: 0-day-to-expiry (0DTE), 1-day-to-expiry (1DTE), 14-plus-day-to-expiry (14D+), closing MOC imbalance.
- No historical backtesting; focus on live data ingestion and decisioning.

## 4. Technology Stack
- Language: Python 3.11 (virtual environment managed locally; packaged via Docker for deployment).
- Dependency management: pip-tools (requirements.in -> requirements.txt).
- Data stores:
  - Redis: live cache, inter-module queues, approval queues, latest analytics and state.
  - Postgres: Unusual Whales WebSocket history, REST data needing lookback, trade and distribution logs (2-year retention), nightly Redis export sink.
- Frontend: React dashboard (Vite or Next.js) for metrics and controls.
- AI: Anthropic Claude Haiku for market commentary and trade explainability.
- Messaging & Social: Discord (premium/basic/free channels), Telegram bot for approvals, Twitter and Reddit APIs for queued posts.
- Infrastructure: Docker/Docker Compose locally; eventual deployment to flexible OS (no longer constrained to Windows Server 2003).
- Runtime versions tracked in `docs/runtime_environment.md` with full `pip freeze` at `docs/runtime_versions.txt`.

## 5. Data Ingestion Overview
### 5.1 Unusual Whales
- Interfaces: REST (120 calls/min cap) and WebSocket channels (flow alerts, GEX, option trades, news, price, etc.).
- Pipeline:
  1. Async WebSocket consumers parse payloads and enqueue structured events.
  2. Redis Hashes/Streams maintain latest hot state for downstream modules.
  3. Batched Postgres inserts persist firehose data for history and analytics replay; REST responses are archived verbatim for later transformation.
- Schema approach:
  - Tables per channel family (e.g., `uw_flow_alerts`, `uw_option_trades`, `uw_gex_snapshot`, `uw_gex_strike`, `uw_gex_strike_expiry`, `uw_news`, `uw_price_ticks`) plus `uw_rest_payloads` for raw REST JSON.
  - Timestamp columns for source and ingestion times; numeric fields typed; raw payload preserved in JSONB for drift checks.
  - Native daily partitioning with retention pruning scripts; nightly exports of Redis trade/distribution logs into Postgres for 2-year retention.

### 5.2 Interactive Brokers (IB)
- Integrations: official TWS API for L1 top-of-book, L2 depth (up to three tickers simultaneously), and 5-second bars.
- Watchdog handles 11:45 PM TWS restart by reconnecting and resubscribing to feeds.
- Redis caches latest quotes/positions; Postgres holds trade logs and any historical metrics required.

## 6. Analytics & Signal Architecture
- Analytics workers subscribe to Redis Streams of ingestion events, compute metrics and forward predictions, and upsert results into Redis Hashes plus Postgres history tables as needed.
- Signal engine consumes analytics outputs to generate strategy-specific signals with structured metadata: signal id, strategy, confidence, feature contributions, rationale, risk inputs.
- Explainability payloads stored both in Redis (for live use) and Postgres (for audit and AI overseer consumption).

## 7. Risk Management & Execution
- Risk rules scope includes capital allocation formulas, max exposure, margin usage, and open PnL checks against live IB account balances.
- Execution engine submits orders via IB API, tracks fills, adjusts trailing stops, and monitors PnL; any state change publishes to Redis for distribution and logging.
- Reconciliation ensures orders remain idempotent (retries safe) and stale signals are discarded if conditions change.

## 8. Distribution & Communication
- Discord publishing: immediate premium message, t+60 seconds basic message (redacted), t+5 minutes free channel (further redacted).
- Distribution events archived in Postgres for retention.
- Profit/loss adjustments or stop changes trigger replies in each channel with identical delay cadence.
- Telegram bot queue: receives packaged messages (trades, AI reports, social posts) for manual approval; approved messages released to Twitter/Reddit and logged.
- AI commentator produces pre-market, intraday, post-market reports, plus trade explainability narratives. Cron scheduler triggers drafts; Telegram approval required before dissemination.

## 9. Dashboard & Operations Controls
- React dashboard displays live system health: Redis memory/keys, ingestion lag, queue depths, Postgres status, open trades, recent alerts.
- Provides manual controls: pause/resume specific feeds, flush caches, override or cancel trades, acknowledge alerts.
- Authentication/authorization kept simple (local credentials or token-based) with documentation for future hardening.

## 10. Observability & Monitoring
- Logging: structured JSON logs per module, centralized via stdout aggregation.
- Metrics: minimal Prometheus exporter exposing ingestion rates, Redis memory, Postgres write latency, execution/risk outcomes; documentation will cover setup and queries for users unfamiliar with Prometheus.
- Alerting: lightweight rule set (e.g., Redis memory high, Postgres lag, IB disconnect) wired to preferred notification channel (to be decided).

## 11. Testing Strategy
- Unit tests for parsers, analytics calculations, risk/execution logic.
- Integration tests hitting live Unusual Whales and IB APIs (credentials loaded from `.env` excluded via `.gitignore`); rate-limited scheduling respects 120 calls/minute and IB session limits.
- Staging scripts simulate end-to-end flow locally using Dockerized Redis/Postgres and optional recorded payloads.

## 12. Deployment & Environment Management
- Local development: `make` tasks for venv setup, dependency sync (pip-tools), lint/test, Docker compose orchestration.
- Docker images prepared for ingestion/analytics/execution services and dashboard; services may run host-level where latency or simplicity benefits.
- Environment variables stored in `.env` (gitignored); secrets mounted or injected in production deploys.
- Nightly jobs: Redis export to Postgres, log rotation, verification of TWS restart handshake.

## 13. Delivery Roadmap
1. **Phase 0** – Scaffold repo, Dockerfiles/compose, base FastAPI skeleton, Redis/Postgres configs, SQL migration folder with manual scripts and runner. ✅
2. **Phase 1** – Implement Unusual Whales REST/WebSocket ingestion, Redis live cache, Postgres persistence, retention/export scripts. ✅ (metrics exporter & REST classification to follow up)
3. **Phase 2** – Integrate IB market data feeds with reconnect watchdog, unify data models across Redis/Postgres.
4. **Phase 3** – Build analytics framework and initial metrics; define message schemas.
5. **Phase 4** – Implement strategy-specific signal engines with explainability outputs.
6. **Phase 5** – Design risk rules and wire execution engine (order management, trailing stops, PnL tracking).
7. **Phase 6** – Build distribution system (Discord tiers, Telegram queue, archival, Twitter/Reddit connectors).
8. **Phase 7** – Implement AI commentator/overseer workflows and cron scheduling with approval gating.
9. **Phase 8** – Deliver React dashboard with health metrics, control surfaces, and audit views.
10. **Phase 9** – Hardening, monitoring rules, Docker image polish, cloud deployment runbook, final documentation.

## 14. Open Decisions & Future Clarifications
- Confirm classification of each Unusual Whales endpoint/channel as Redis snapshot, Postgres archive, or future derived table (Phase 2 follow-up).
- Detailed risk formulas (capital allocation, stop logic) to be designed during Phase 5.
- Alerting destination for monitoring (e.g., email, Telegram) to be chosen.
- Any further documentation sources required; browser access will be used to fetch official API docs when necessary upon user request.

## 15. Next Immediate Actions
- Prepare `.gitignore` to exclude `.env` and other sensitive files once repo scaffolding begins.
- Confirm acceptable cadence for live API integration tests to stay within usage limits.
- After approval of this scope, proceed to build supporting templates and scripts in Phase 0. ✅ *Completed.*
- Begin Phase 1 by cataloging Unusual Whales REST endpoints and defining ingestion adapters.
