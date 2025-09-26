# Alpha Vantage Ingestion Verification – 2025-09-26

## Test Environment
- API tier: Premium (documented 600 requests/minute limit)
- Window: 2025-09-26 09:32–09:39 UTC
- Endpoints covered: `REALTIME_OPTIONS`, `MACD`, `BBANDS`, `VWAP`
- Tooling: project virtualenv with `.venv/bin/python`, Redis on `redis://localhost:6379/0`

## Phase 1 – Basic Functionality
- Ran `REALTIME_OPTIONS` for three symbols (`SPY`, `QQQ`, `NVDA`).
- Payload sizes: 4.3 MB (SPY), 3.6 MB (QQQ), 1.7 MB (NVDA).
- Redis keys `raw:alpha_vantage:realtime_options:{symbol}` created with TTL 30 s and heartbeats `state:alpha_vantage:realtime_options:{symbol}` reporting `status=ok`.

## Phase 2 – Concurrent Load
- Sequential sweep: 5 consecutive runs × 8 symbols × 1 endpoint → 40 calls.
- Parallel sweep: all three technical endpoints across 17 symbols (51 concurrent calls).
- Completion times:
  - `MACD`: 17 symbols in ~10 s, TTL 300 s confirmed.
  - `BBANDS`: 17 symbols in ~12 s, TTL 300 s confirmed.
  - `VWAP`: 17 symbols in ~6 s, TTL 300 s confirmed.
- Aggregate: 91 API calls within ~30 s, zero failures.

## Phase 3 – Burst / Rate-Limit Probe
- Config: 50 parallel processes, single endpoint (`REALTIME_OPTIONS`), target 12 rounds × 68 calls (816 attempts).
- Observed burst: 50 simultaneous calls completed between 09:39:24–09:39:28 UTC.
- Sustained throughput: ~12.5 calls/second with 100 % success.
- No throttling responses (`429`, `Note`, `Information`, `Error Message`) encountered; premium tier absorbed the burst.

## Redis Spot Checks
- Data keys: `raw:alpha_vantage:macd:SPY` (1.8 MB), `raw:alpha_vantage:bbbands:NVDA` (2.3 MB), `raw:alpha_vantage:vwap:AMZN` (0.8 MB), `raw:alpha_vantage:realtime_options:SPY` (4.3 MB).
- Heartbeat example (`state:alpha_vantage:macd:SPY`):
  - `status=ok`
  - `timestamp=2025-09-26T13:34:30.115535+00:00`
  - `ttl_seconds=300`
  - `cadence_seconds=30`

## Findings
- ✅ Shared `AlphaVantageIngestionRunner` successfully drives all endpoints; Redis payload shape and heartbeat metadata consistent project-wide.
- ✅ Concurrency up to 50 parallel requests remains stable; no dropped writes or stale heartbeats observed.
- ✅ HTTP retry configuration includes `429` handling and is covered by unit tests.
- ⚠️ Due to premium entitlement, throttling payloads were not observed during live testing; rely on automated tests (`tests/ingestion/alpha_vantage/test_shared.py`) plus future captures if tier changes.

## Follow-up
- Keep capturing fresh verification artifacts as payloads evolve; prune `docs/verification/` as needed.
- Consider scheduling synthetic throttling tests (mock server) if production tier continues to mask 429 responses.
