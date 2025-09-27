# Quanticity Capital Options System – Master Plan

## Implementation Status (October 2025)
- 🚧 **Current baseline:** documentation, sample payloads, and pinned dependencies only. No source
  packages, configuration files, or tests exist yet.
- 🗂️ **Short-term focus:** rebuild the repository skeleton (see `docs/implementation_plan.md`) before
  writing ingestion code.
- 📌 **Future phases:** Alpha Vantage ingestion, IBKR connectivity, analytics, signal engine, and
  downstream modules remain aspirational until their prerequisites land.

> **A note on scope:** Everything that follows describes the desired end state. Treat the sections
> below as design targets to revisit once the corresponding code and configuration files exist.

## 1. Purpose and Vision
Build a MacBook-first automated options trading stack that ingests live data, performs institutional-grade analytics, generates and executes signals, and publishes outputs across trading and social channels. The system must remain understandable, modular, and redis-centric, with Redis acting as the data exchange hub between independently deployable modules orchestrated by a single `main.py` runtime.

## 2. Guiding Principles
- **Simplicity first:** python 3.11, single-node Redis, local Postgres, optional Google Cloud later.
- **Module isolation:** modules communicate only through Redis and, for persistence, Postgres. Direct module-to-module calls are disallowed.
- **Rate-aware at source:** schedulers enforce Alpha Vantage and IBKR limits; downstream modules rely on TTL freshness guarantees.
- **Real data only:** integration tests hit live services and assert on actual Redis/Postgres state—no mocks.
- **Human oversight:** OpenAI watchdog augments analytics and comms but never bypasses manual override unless explicitly toggled.
- **Operational transparency:** comprehensive logging, dashboard visibility, and failure notifications without complex infrastructure.

## 3. High-Level Architecture
```
+-------------------+
|  main.py          |
|  Orchestrator     |
+---------+---------+
          |
  +-------+------+---------------------------+
  |              |                           |
Scheduler   Health Monitor             Failure Alerts
  |
  v
+-----------------+      +-----------------+
| Redis (pub/sub) |<---->| Postgres (OLTP) |
+-----------------+      +-----------------+
  ^        ^   ^                ^
  |        |   |                |
  |        |   |                +--> Trade archive & analytics history
  |        |   +--------+
  |        |            |
  |   +----+----+  +----+------+  +---------------+  +----------------+
  |   | Ingestion|  | Analytics |  | Signal Engine |  | Execution/Risk|
  |   +----+----+  +----+------+  +-------+-------+  +--------+-------+
  |        |            |                 |                 |
  |        |            v                 v                 v
  |  +-----+-----+  +---+------+  +------+-----+   +---------+---------+
  |  | Scheduler |  | Watchdog |  | Social Hub |   | Dashboard API/UI |
  |  +-----------+  +----------+  +------------+   +------------------+
```

### Core Modules
- **Scheduler & Rate Controller:** central timing loop that queues work respecting API constraints and Redis TTLs.
- **Ingestion Suite:** Alpha Vantage, IBKR, macro/futures processors writing normalized payloads to Redis.
- **Analytics Engine:** consumes cached data, calculates dealer analytics, risk metrics, macro overlays, and writes structured analytics objects.
- **Signal Engine:** interprets analytics for each strategy, applies guardrails (Kelly/Achilles), and posts signal objects.
- **Execution & Risk:** submits orders through IBKR, manages lifecycle, and mirrors state to Redis + Postgres.
- **OpenAI Watchdog:** validates analytics/signals, generates commentary, and assists social messaging with manual/auto approval modes.
- **Social Broadcast Hub:** formats and dispatches updates to Discord, Twitter, Telegram, Reddit via respective APIs/webhooks.
- **Dashboard API + React UI:** exposes module health, data freshness, positions, trade logs, and content pipeline status.
- **Observability:** structured logs with rotation, Redis key expirations to detect stale data, alerting hooks for module crashes.

## 4. Redis Namespace & TTL Scheme
Key pattern: `scope:module:entity[:context]`. All keys store JSON unless noted. TTLs sized to exceed fetch cadence by ~2x to prevent gaps during retries.

| Scope | Example Key | Description | TTL | Refresh Cadence |
|-------|-------------|-------------|-----|-----------------|
| `raw:alpha_vantage:realtime_options:{symbol}` | `raw:alpha_vantage:realtime_options:SPY` | AV options chain payload | 30s | 10s per symbol |
| `raw:alpha_vantage:time_series_intraday:{symbol}` | `raw:alpha_vantage:time_series_intraday:NVDA` | AV 1‑minute price feed | 60s | 30s |
| `raw:alpha_vantage:top_gainers_losers` | `raw:alpha_vantage:top_gainers_losers` | Daily US market movers snapshot | 300s | 180s |
| `raw:alpha_vantage:news_sentiment:{symbol}` | `raw:alpha_vantage:news_sentiment:AAPL` | AV news sentiment per equity | 900s | 600s |
| `raw:ibkr:quotes:{symbol}` | `raw:ibkr:quotes:SPY` | IBKR top-of-book quotes | 6s | 3s |
| `raw:ibkr:l2:{symbol}` | `raw:ibkr:l2:SPY` | IBKR level-2 depth snapshot | 10s | 5s rotation |
| `raw:ibkr:account:summary` | `raw:ibkr:account:summary` | IBKR account metrics | 30s | 15s |
| `raw:ibkr:account:positions` | `raw:ibkr:account:positions` | STK/OPT positions snapshot | 30s | 15s |
| `raw:ibkr:account:pnl` | `raw:ibkr:account:pnl` | Account PnL (daily/unrealized/realized) | 30s | 15s |
| `raw:ibkr:position:pnl:{symbol}` | `raw:ibkr:position:pnl:SPY` | Per-symbol PnL snapshot | 30s | 15s |
| `stream:ibkr:executions` | `stream:ibkr:executions` | IBKR executions + commissions | stream (maxlen 5000) | on event |
| `raw:macro` | `raw:macro:real_gdp` | Macro series | 12h | 6h |
| `derived:analytics` | `derived:analytics:SPY` | Aggregated analytics bundle | 20s | 10s |
| `derived:correlation` | `derived:correlation:equities` | Correlation matrix snapshot | 15m | 5m |
| `derived:vol_regime` | `derived:vol_regime:SPY` | Volatility regime classification | 2m | 1m |
| `signal:pending` | `signal:pending:SPY:0dte` | Pending signal awaiting approval | 30m | on demand |
| `signal:active` | `signal:active:trade_id` | Live trade signal state | 2h | heartbeat 5s |
| `exec:order` | `exec:order:trade_id` | Execution status and fills | 2h (extends) | on fill updates |
| `trade:summary` | `trade:summary:2025-09-25` | Daily trade rollup | 7d | end-of-day |
| `social:queue` | `social:queue:discord:message_id` | Message awaiting send/approval | 2h | on creation |
| `watchdog:review` | `watchdog:review:trade_id` | OpenAI review payload | 1h | on signal creation |
| `system:heartbeat` | `system:heartbeat:<module>` | Liveness heartbeat | 30s | module-specific |

Default serialization via `orjson`; large payloads may leverage Redis Streams for append-only logs (`stream:trades`, TTL disabled).

## 5. Symbol Universe & Scheduling Defaults
### Equities & ETFs
- **Techascope Equities (14):** NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD.
- **Index ETFs:** SPY, QQQ, IWM (0DTE & 1DTE focus).

### Futures (starter list)
ES, MES, NQ, MNQ, RTY, CL, ZN, GC. Additional contracts can be configured in `config/symbols.yml` with cadence overrides.

### Alpha Vantage Cadence (600 cpm budget)
- Realtime options chains: 17 symbols @ 10s cadence ⇒ ~102 req/min.
- Technical indicators (VWAP/MACD/BBANDS): sequential sweep every 30s ⇒ ~102 req/min across three endpoints.
- Analytics Sliding Window (multi-symbol batches of 10) every 5m ⇒ ~2 req/min.
- News & sentiment (14 equities, no ETFs) every 10m ⇒ ~6 req/min.
- Top gainers/losers every 2m ⇒ 0.5 req/min.
- Macro series (GDP/CPI/Inflation) every 6h ⇒ negligible.
- Shares outstanding & earnings estimates weekly at market close ⇒ negligible.
- Earnings transcripts on-demand (triggered by schedule or upcoming events).
Budget headroom ≈ 388 req/min reserved for bursts and retries. Scheduler enforces per-endpoint cooldowns.

### IBKR Cadence & Rotation
- Level-2 market depth: rotate symbols in trios every 5s (five groups covering 15 symbols, remainder pair fills slot). Each subscription receives 15s of data before rotation; TTL 10s ensures freshness.
- Top-of-book quotes: persistent subscriptions for traded symbols (SPY/QQQ/IWM + active trades) with 3s update expectation.
- Account, PnL, and positions: poll every 15s; daily snapshots archived to Postgres end-of-day.
- Execution reports: streaming callback; store immediately.

## 6. Data Lifecycle
1. **Ingestion:** scheduler issues job → connector fetches data → normalized payload stored under `raw:*` key with TTL → metadata heartbeat set.
2. **Analytics:** pull latest `raw:*` data; compute dealer greeks, VPIN, volatility regime, etc.; write consolidated analytics to `derived:*` keys and push updates to Redis Stream `stream:analytics` for historical replay.
3. **Signal:** evaluate analytics vs. strategy playbooks; create `signal:pending` entries. OpenAI watchdog receives payload for validation and commentary.
4. **Execution:** once approved, orders executed via IBKR; execution state stored under `exec:*` keys; trade lifecycle appended to Postgres tables.
5. **Social & Reporting:** social hub formats updates using analytics, signals, and trades; posts or queues by tier; logs to Redis and Postgres.
6. **Dashboard:** API aggregates state from Redis, with historical queries served from Postgres.

## 7. Storage & Schema Overview
- **Redis:** primary cache/event bus. Use logical DB 0 with namespacing. Employ `SCAN`-free design by maintaining index keys (`index:signals:active`).
- **Postgres (Homebrew):** transactional history with schemas:
  - `reference`: symbols, expirations, strategy configs.
  - `trading`: trades, fills, risk metrics snapshots.
  - `analytics`: aggregated analytics snapshots, macro history.
  - `audit`: social posts, watchdog approvals.
  - Provide SQL migrations via `alembic`.

## 8. Scheduler & Orchestration
- Single orchestrator spawns async tasks (e.g., `asyncio`, `apscheduler`) with priority queue.
- Scheduler maintains per-endpoint token buckets and symbol queues, persisting state in Redis (`system:schedule:*`) for crash recovery.
- Failure policy: exponential backoff with jitter, classify errors (transient vs. fatal) with max retry count before raising alert.

## 9. OpenAI Watchdog (Concept)
- Observes analytics and signals via Redis Streams.
- Modes: `manual` (default) requires human approval via Telegram bot command; `autopilot` publishes when thresholds satisfied.
- Responsibilities: flag incoherent analytics, generate trade narrative, produce tiered social summaries.
- Provide configurable guardrails (max tokens per minute, fallback to local rules when offline).

## 10. Social Distribution Strategy
- **Discord:** three-tier channels (free/basic/premium). Scheduled daily cadences (pre-market, midday, close) configurable in Redis.
- **Twitter (X):** concise trade blotter + key stats; rate-limited to avoid duplication.
- **Telegram:** manual approval workflow; ability to forward to other channels.
- **Reddit:** longer-form posts for premium recaps.
- Social hub uses templating (Jinja2) with message blueprints stored in Postgres (`audit.social_templates`).

## 11. Dashboard Concept
- Backend: FastAPI serving data from Redis/Postgres, provides websocket for live metrics.
- Frontend: TypeScript React SPA (Vite) with panels for ingestion health, analytics snapshots, signals/executions, social queue, watchdog status, futures overlays.
- Authentication optional for local use; basic token if deployed externally.

## 12. Logging & Alerting
- Use `structlog` or Python logging with JSON formatter. Output to console + rotating file (`logs/system.log` at 50 MB x 5 files).
- Each module emits heartbeat key and structured health message.
- Alerting via email/Telegram webhook when module heartbeat expires or fatal errors occur.

## 13. Testing & Validation
- Integration tests executed manually with environment variables for live keys; test harness captures request metadata and resultant Redis/Postgres rows.
- Provide CLI tools to inspect latest payloads (`python tools/peek.py raw:options:SPY`).

## 14. Deployment & Operations
- MacBook default: `poetry` or `uv` for dependency management, `direnv` for env vars.
- Services run within tmux or `honcho` (Procfile) for local multi-process management.
- For Google Cloud extension, package as Docker images with environment parity.

## 15. Security & Secrets
- `.env` file managed locally; secrets never committed.
- Rotating Alpha Vantage/IBKR/OpenAI tokens handled via environment.
- Limit outbound posts through approval workflows where possible.

## 16. Known Constraints & Non-Goals
- No high-availability requirements initially; single-node suffices.
- No complex SSL or kubernetes orchestration until needed.
- No synthetic data or mocking frameworks.
- Focus on clarity over automation; automation added only when clearly useful.

## 17. Ingestion Reset (September 2025)
- The initial Alpha Vantage implementation overreached (unsupported symbols, ad-hoc Redis tuning, multi-process orchestration). The code has been pared back to a clean baseline so we can rebuild deliberately.
- New ingestion work must start from the existing specs, with explicit capability mapping (realtime ETFs vs. equity option-chain endpoints), first-class retry/backoff, and measured concurrency.
- Redis stays simple until benchmarks demand otherwise; the health monitor remains the single source of freshness/back-pressure.
- Next actions live in `docs/implementation_plan.md` and the intake tables inside
  `docs/alpha_vantage_endpoints.md`; create new specs alongside the code when work restarts.
