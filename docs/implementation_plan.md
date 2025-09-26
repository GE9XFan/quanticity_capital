# Implementation Plan

## Phase 0 – Environment & Tooling (Day 0)
- Install Python 3.11, Redis (brew), Postgres (brew), Node 20 (for dashboard).
- Create repo scaffolding: `src/`, `docs/`, `config/`, `tests/`, `tools/`.
- Add dependency manager (`poetry` or `uv`), linting/formatting (ruff, black), type checking (mypy), task runner (`make` or `just`).
- Configure logging directory (`logs/`) and sample `.env.example` with placeholders for Alpha Vantage, IBKR, OpenAI, socials.

## Phase 1 – Core Infrastructure (Day 1-2)
- Implement configuration loader (Pydantic) reading `.env` + YAML symbol settings.
- Build Redis client wrapper (retry, serialization, TTL helpers, index maintenance).
- Define Postgres connection with SQLAlchemy + Alembic baseline migrations (schemas `reference`, `trading`, `analytics`, `audit`).
- Create shared models (Pydantic) for options chains, analytics bundles, signals, orders, social posts.

## Phase 2 – Scheduler & Orchestrator (Day 2-4)
- Bootstrap structured logging (Structlog + stdlib) and Redis dependency wiring for the
  orchestrator entry point.
- Implement the orchestrator with `asyncio.TaskGroup`, module toggles from `config/runtime.yml`,
  lifecycle event stream, and aggregated heartbeat status in Redis.
- Deliver the scheduler runtime: token buckets, rotation queues, Redis-backed state persistence,
  and a `snapshot()` hook for future CLI inspection.
- Ensure orchestrator ↔ scheduler integration (heartbeat propagation, failure escalation,
  graceful shutdown).
- Document verification steps (Redis commands for heartbeats/state) and add targeted unit tests for
  orchestrator + scheduler behaviour.

## Phase 3 – Alpha Vantage Ingestion (Day 4-7)
- Implement reusable HTTP client with exponential backoff and concurrency caps.
- Build data fetchers:
  - Realtime options (with Greeks) for ETFs + Techascope equities.
  - Technical indicators (VWAP, MACD, BBANDS) per cadence.
  - Analytics Sliding Window batches for specified calculations.
  - Macro endpoints (GDP, CPI, Inflation) and Top gainers/losers.
  - Shares outstanding, earnings estimates, transcripts, news sentiment.
- Normalize payloads, enforce TTL scheme, and log metadata.
- Write integration scripts to validate live storage in Redis (`tools/verify_av.py`).

## Phase 4 – IBKR Connectivity & Market Data (Day 7-11)
- Research latest IBKR TWS connection patterns; adopt `ib_insync` or official API wrapper with async compatibility.
- Implement connection manager handling client ID allocation, auto-reconnect, and gateway heartbeat.
- Build data listeners for level-2 rotation, top-of-book, account summary, positions, PnL, and order status.
- Normalize to Redis format; ensure TTLs align with scheduler expectations.
- Create diagnostics CLI for connection state and subscription queue.

## Phase 5 – Analytics Engine (Day 11-16)
- Implement analytics pipeline framework (scheduled tasks that read `raw:*` keys and emit `derived:*`).
- Develop metrics modules per requirement: dealer Greeks & exposures, VPIN, volatility regime, liquidity stress, volume/OI anomaly, correlation matrix, MOC imbalance, macro overlays, futures linkage, risk summary, IV surface curvature/smile skew, risk reversal ladder, cross-asset stress index, dealer edge attribution.
- Cache intermediate outputs in Redis Streams and Postgres snapshots.
- Validate calculations with sample live data captures and produce summary logging.

## Phase 6 – Signal Engine (Day 16-20)
- Define strategy templates (0DTE, 1DTE, 14DTE, MOC imbalance) with thresholds referencing analytics metrics.
- Implement toggles for Kelly vs. Achilles sizing per strategy; store parameters in Postgres `reference.strategy_config`.
- Create signal evaluation loop writing `signal:pending` entries, with change detection and duplicate suppression.
- Integrate with OpenAI watchdog pipeline for review requests.

## Phase 7 – Execution & Risk Engine (Day 20-25)
- Implement order translation layer from internal signal format to IBKR API objects (single-leg only).
- Manage order lifecycle: submit, monitor status, handle partial fills, update stops/targets, trailing adjustments.
- Implement risk guardrails (exposure caps, Kelly/Achilles outputs, session loss limits).
- Persist trades/fills to Postgres; mirror state in Redis (`exec:*`, `trade:summary`).
- Build manual override CLI for order cancel/amend.

## Phase 8 – OpenAI Watchdog (Day 25-28)
- Define payload schema for watchdog requests (analytics snapshot + proposed signal).
- Implement review workflow with manual default: store requests, await Telegram approval, or auto-publish when autopilot enabled.
- Generate narrative commentary and risk flags; write outputs to `watchdog:review` and `social:queue` when approved.
- Provide throttling controls and error fallback (manual-only mode if API unavailable).

## Phase 9 – Social Distribution (Day 28-31)
- Implement social message templating (Jinja2) with tier metadata (Discord free/basic/premium).
- Build connectors for Discord webhooks, Twitter API, Telegram bot, Reddit API; include rate-limit handlers.
- Create scheduling rules for daily cadences and event-driven posts (entries/exits, end-of-day recap).
- Store posts in Postgres `audit.social_posts` with status and timestamps.

## Phase 10 – Dashboard & API (Day 31-36)
- Build FastAPI backend exposing health, data freshness, signals, trades, social queue, watchdog state, futures overlays.
- Implement WebSocket updates for key dashboards (ingestion health, live trades).
- Scaffold React (Vite + TypeScript) frontend with panels and modular components; integrate with backend endpoints.
- Add simple auth token (optional) and environment-based configuration.

## Phase 11 – Observability & Tooling (Day 36-38)
- Finalize logging strategy with rotation, context-aware tags, and failure alerts to Telegram/email.
- Implement heartbeat monitor that scans Redis `system:heartbeat:*` and raises notifications.
- Add CLI utilities for data inspection, scheduler management, and manual signal approval.

## Phase 12 – Integration Testing & Hardening (Day 38-42)
- Execute end-to-end dry runs against paper account with Alpha Vantage live data.
- Capture sample payloads and store in `docs/test-records/` for regression reference.
- Document runbooks (start/stop system, rotate keys, recover from failures).
- Review resource usage, rate-limit adherence, and refine cadences/TTLs as needed.

## Phase 13 – Deployment Prep (Optional)
- Containerize services (Docker) while preserving MacBook workflow.
- Define Google Cloud deployment approach (single VM, systemd services, managed Postgres) for future scaling.
- Outline backup and disaster recovery steps for Postgres/Redis snapshots.

## Continuous Workstreams
- **Documentation:** keep module specs and runbooks updated per iteration.
- **Security:** rotate keys, review API usage, and limit credentials exposure.
- **Feedback loop:** incorporate user feedback, adjust strategies, expand symbol universe as needed.
