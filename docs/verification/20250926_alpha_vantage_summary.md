# Alpha Vantage Ingestion Verification – 2025-09-26

## Execution Overview
- All four implemented endpoints (`REALTIME_OPTIONS`, `VWAP`, `MACD`, `BBANDS`) were executed inside the project virtual environment using real credentials from `.env`.
- Each CLI was run twice: a single-symbol dry run (`--symbol TSLA`) followed by a full-basket run covering 17 symbols (SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD).
- Resulting payloads, TTLs, and heartbeats were inspected in Redis via `redis-cli`.

## Verification Results
- **REALTIME_OPTIONS**
  - Redis key pattern: `raw:alpha_vantage:realtime_options:{symbol}`
  - TTL confirmed at 30 seconds; expected expirations observed between checks.
  - Heartbeat keys `state:alpha_vantage:realtime_options:{symbol}` report `status=ok` with timestamps aligned to the last fetch.
- **VWAP**, **MACD**, **BBANDS**
  - Redis key pattern: `raw:alpha_vantage:<endpoint>:{symbol}`
  - TTL confirmed at 300 seconds for all symbols with decrementing TTL values on repeated reads.
  - Heartbeats show `status=ok`, carrying TTL and cadence metadata.

## Redis Snapshot Summary
- 52 live data keys after the final full-basket run (17 symbols × 3 long-lived endpoints + transient call data).
- Verification artifacts: `realtime_options_20250926.json`, `vwap_20250926.json`, `macd_20250926.json`, `bbands_20250926.json` capture representative payloads and TTLs.

## Next Monitoring Steps
- If continuous ingestion is desired, schedule each CLI at its cadence (cron/launchd/systemd) and consider alerting on heartbeat staleness.
- Periodically prune `docs/verification/` with newer captures to keep regression artifacts current.
