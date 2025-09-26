# Alpha Vantage Ingestion Module – Reset Plan (September 2025)

## Goal
Rebuild the Alpha Vantage ingestion suite from a clean slate. The previous implementation accumulated unsupported symbol calls, ad-hoc concurrency tuning, and multi-process orchestration that became unmanageable. This plan sets the targets and guardrails for the new build.

## Scope (Phase 1)
1. **Realtime Options (ETF + Techascope equities)**
   - Endpoint: `REALTIME_OPTIONS`.
   - Symbols: SPY, QQQ, IWM plus the Techascope equities universe. Alpha Vantage currently serves these when `require_greeks=true` is supplied.
   - Cadence: every 6s with per-symbol staggering.
   - Output: `raw:options:<symbol>` JSON payloads + heartbeat key `state:ingestion:options:<symbol>`.
2. **Technical Indicators (same symbol set)**
   - Initial set: VWAP (1m), MACD (1m), BBANDS (daily).
   - Symbols: mirror the realtime options list so analytics share a uniform coverage map.
   - Cadence: every 30s per symbol.
   - Output: `raw:indicator:<symbol>:<indicator>`.
3. **Top Gainers / Losers**
   - Endpoint: `TOP_GAINERS_LOSERS`
   - Cadence: every 2m.
   - Output: `raw:market_movers`.
4. **News Sentiment (equities only)**
   - Endpoint: `NEWS_SENTIMENT`
   - Symbols: Techascope equities list (AV supports single-stock news).
   - Cadence: every 10m.
   - Output: `raw:news:equities` (aggregate) plus future per-symbol expansion.

Phase 1 explicitly excludes single-stock option chains, analytics window batches, and macro series. Those will be reintroduced once the framework is stable.

## Design Requirements
- **Capability Map:** Configuration must identify which symbols are permitted per endpoint; unsupported requests are never issued.
- **Single Orchestrator:** Ingestion runs within the main runtime. No sidecar processes or bespoke launch scripts.
- **Bounded Concurrency:** Shared async semaphore per endpoint group (start with 4) plus backoff handling.
- **Retry Strategy:** Three attempts per request with exponential backoff (1s, 3s, 7s). After final failure, record a cooldown timestamp and skip the symbol for one cadence.
- **Redis Usage:** Simple singleton client; pipelining only when multiple writes are unavoidable. Keys store `{ "symbol": ..., "as_of": ..., "data": ... }` payloads with TTL = 2× cadence.
- **Metrics:** Heartbeat timestamps + error counters per job under `state:ingestion:*`. No bespoke metric hashes in phase 1; health monitor is the source of truth.
- **Logging:** Structured log entry for each request (start, success, failure). Error logs must include HTTP status and truncated body.

## Configuration
- Extend `config/symbols.yml` with capability flags:
  ```yaml
  ingestion:
    av:
      realtime_options: [SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD]
      tech_indicators: [SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD]
      news_sentiment: [NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD]
  ```
- Scheduler job cadences remain defined in `config/schedule.yml`.
- Env var: `ALPHAVANTAGE_API_KEY`.

## Deliverables
1. New ingestion framework (`src/services/ingestion/alpha_vantage/`) implementing the scope above.
2. Updated health monitor to flag missing ETF options/indicators and news payloads.
3. Integration checks verifying Redis keys, TTLs, and log outputs for one full cadence.

## Out of Scope (Phase 1)
- Single-stock option chains (requires `OPTION_CHAIN` endpoint + paging).
- Analytics sliding window batches.
- Macro/fundamental endpoints.
- IBKR ingestion (separate spec).

## Next Steps After Phase 1
- Extend capability map with per-endpoint parameters, then add equity option ingestion using the correct API.
- Introduce macro/fundamental fetches with slower cadences.
- Revisit connection pooling only if metrics show Redis saturation.
