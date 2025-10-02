# IBKR Market-Depth Ingestion

This slice covers the dedicated IBKR Level 2 feed described in the architecture doc. It resolves concrete venues (no SMART routing), rotates at most three concurrent subscriptions, adapts to IBKR depth limits, and mirrors every update into Redis streams/hashes with heartbeats for liveness checks.

### What the implementation does

- Connects to TWS/Gateway with automatic client-id negotiation and reconnect-safe settings.
- Resolves contracts with venue overrides (`ISLAND` for NASDAQ names, `ARCA` for ETFs) and stores whether a symbol actually supports L2.
- Maintains a rotating window of ≤3 depth subscriptions, shrinking/expanding based on error 309 pressure.
- Captures reqIds explicitly so every unsubscribe releases the slot—preventing phantom 309s from accumulating.
- Normalizes each book to 10 levels and persists to Redis using the architecture’s stream/hash/heartbeat pattern.
- Ships two CLIs: `ibkr_depth_probe` for spot checks and `ibkr_ingest_run` for continuous rotation.

## Environment Variables

| Key | Default | Purpose |
| --- | --- | --- |
| `IBKR_HOST` | `127.0.0.1` | IBKR TWS/Gateway host (paper: localhost) |
| `IBKR_PORT` | `7497` | IBKR TWS/Gateway port (paper trading) |
| `IBKR_CLIENT_ID` | `777` | Preferred client ID; auto-increments on conflict |
| `IBKR_CLIENT_ID_MAX_OFFSET` | `5` | How many additional IDs to try before failing |
| `IBKR_DEPTH_ROWS` | `10` | Depth levels per side to request |
| `IBKR_MAX_CONCURRENT_DEPTH` | `3` | Max simultaneous L2 subscriptions |
| `IBKR_ROTATION_SECS` | `15` | Dwell time before rotating to the next batch |
| `IBKR_STREAM_MAXLEN` | `10000` | Redis stream maxlen (approximate) |
| `IBKR_HEARTBEAT_TTL` | `30` | Heartbeat TTL in seconds |
| `IBKR_ERROR309_COOLDOWN_SECS` | `8` | Cooldown after hitting error 309 |
| `IBKR_ERROR309_RECOVERY_CYCLES` | `4` | Stable rotations before expanding back to three subs |
| `IBKR_LOG_LEVEL` | `INFO` | Structlog log level |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis target used by the ingestion sink |
| `SYMBOL_CONFIG_PATH` | `config/ibkr_symbols.yaml` | YAML Universe + venue overrides |

## Symbol Universe & Exchanges

`config/ibkr_symbols.yaml` now defaults to the 11 live names we ingest:

```
SPY, QQQ, IWM,
AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA,
SPX is intentionally omitted by default (see below)
```

The resolver enforces explicit venues so L2 never falls back to SMART routing:

- NASDAQ listings (AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, QQQ) → `exchange=ISLAND`, `primaryExchange=NASDAQ`.
- ETFs on NYSE Arca (SPY, IWM) → `exchange=ARCA`, `primaryExchange=ARCA`.

If you add SPX or other non-venue-supported tickers, the resolver will still attempt `CBOE`; unsupported contracts produce a WARN and are skipped without breaking rotation. Overrides in the YAML can force venues if IB returns an unexpected exchange. The resolver will still prefer real venues from `validExchanges` while keeping concrete (non-SMART) routing.

## Redis Schema

Each symbol writes to three keys that align with the architecture:

- `raw:ibkr:depth:stream:{SYMBOL}` stream (MAXLEN ≈ `IBKR_STREAM_MAXLEN`) with fields: `ts` (unix ms), `bids` (JSON list of 10 `[price, size, venue]` rows), `asks`, `seq` (monotonic per symbol), `venue` (subscription venue).
- `raw:ibkr:depth:last:{SYMBOL}` hash storing `ts`, `bid0`, `ask0`, `bids_json`, `asks_json`, `venue`, `seq` for fast lookups.
- `raw:ibkr:depth:hb:{SYMBOL}` heartbeat key (`SETEX` with TTL ≥ max(`IBKR_HEARTBEAT_TTL`, `rotation_window`, 30)), where `rotation_window = IBKR_ROTATION_SECS × ceil(symbols / IBKR_MAX_CONCURRENT_DEPTH)`.

### October 2025 hardening

- Stream namespace now consistently uses the `raw:ibkr:depth:stream:{symbol}` pattern and snapshots include the write `seq`, enabling deterministic audits.
- Heartbeat TTL is computed dynamically from the full rotation window so the key never expires between batches, even with larger symbol sets.
- Ingestion wraps IBKR's `updateMktDepthL2` with bounds-checking and requests extra depth rows, preventing the `IndexError: list assignment index out of range` spam seen with earlier builds.

## Rotation & Throughput

- Rotation windows are bounded by `IBKR_MAX_CONCURRENT_DEPTH` (default 3) with a dwell of `IBKR_ROTATION_SECS` seconds per batch (default 15). Tweak these envs to tighten the cycle (e.g., set dwell to 8s during high-volatility sessions).
- Every subscribe/unsubscribe logs actual IBKR reqIds, making it easy to correlate with the gateway log.
- The handler normalizes domBids/domAsks into fixed 10-level arrays before persist, so downstream consumers get symmetrical shapes.

## Error 309 Handling

IBKR limits the number of concurrent depth subscriptions. When error 309 appears, the rotation controller:

1. Shrinks the batch size (3 → 2 → 1) immediately and logs the event.
2. Sleeps for `IBKR_ERROR309_COOLDOWN_SECS` before retrying.
3. Tracks stable rotations; after `IBKR_ERROR309_RECOVERY_CYCLES` without new 309s (and after the cooldown window), it ramps the batch back toward three concurrent subscriptions.
4. Because we now record reqIds and cancel them explicitly, stale subscriptions are released as soon as a batch ends. If you still see 309s, another client or TWS window is holding depth slots—check those before blaming the ingest runner.

## Quick Start

1. **Update env + symbols** (if needed):
   ```bash
   cp .env.example .env  # if you have not already
   # edit IBKR_* values and config/ibkr_symbols.yaml as needed
   ```
2. **Run a probe first** (double-check venues, smart depth disabled):
   ```bash
   python3 scripts/ibkr_depth_probe.py --symbol AAPL --symbol2 MSFT
   ```
3. **Start full ingestion**:
   ```bash
   python3 scripts/ibkr_ingest_run.py run
   ```
   Logs stream in JSON (structlog) showing rotation batches, Redis persistence counts, error 309 adaptation, and per-symbol heartbeats each cycle.

Use Ctrl-C to stop ingestion; the runner cancels all depth subscriptions (by reqId), flushes Redis writes, and disconnects from TWS cleanly.

### Operational checks

- **Redis stream sample**:
  ```bash
  redis-cli XREVRANGE raw:ibkr:depth:stream:SPY + - COUNT 3
  ```
- **Snapshot + heartbeat**:
  ```bash
  redis-cli HGETALL raw:ibkr:depth:last:QQQ
  redis-cli GET raw:ibkr:depth:hb:QQQ
  redis-cli TTL raw:ibkr:depth:hb:QQQ
  ```
- **Log tail** (JSON via structlog):
  ```bash
  tail -f ibkr_ingest.log | jq '.'   # assuming you redirect process output
  ```

## My Real Environment Checklist

- `IBKR_HOST`/`IBKR_PORT` match your TWS/Gateway instance (paper → 127.0.0.1:7497).
- `IBKR_CLIENT_ID` is free; increase if another process already uses it.
- Redis is reachable at `REDIS_URL`.
- `config/ibkr_symbols.yaml` covers your current universe plus any venue overrides.
- `IBKR_ROTATION_SECS` and `IBKR_MAX_CONCURRENT_DEPTH` are appropriate for the session (lower dwell during volatile periods).

## Notes

- SPX depth is often unavailable; it is no longer in the default universe, but if you re-enable it expect WARN logs and a skipped rotation slot.
- Level 2 requests always set `isSmartDepth=False`; explicit reqIds guarantee we cancel before loading the next rotation batch, preventing phantom 309s.
- Integration scripts intentionally avoid mocks—run them against a live paper or production IBKR session.
- If Redis logs start showing `redis_write_failed`, check connectivity or authentication; writes are now sequential, so one failing command stops that snapshot while logging the underlying exception.

## Troubleshooting

- **Repeated 309 errors**: Confirm no other tool (TWS depth window, book trader, third-party app) is streaming depth. With this runner alone you should see *zero* 309s thanks to explicit reqIds. If they persist, reduce `IBKR_MAX_CONCURRENT_DEPTH` temporarily and inspect other consumers.
- **Heartbeat expires overnight**: Expected—markets are closed. During live hours, a missing heartbeat means either IBKR throttled us (check logs) or Redis is unreachable.
- **No Redis writes**: Ensure `REDIS_URL` is reachable. The runner logs the first failing command; use that to diagnose auth/network issues.
- **Need faster rotations**: Decrease `IBKR_ROTATION_SECS` (e.g., 8) or limit the universe in `config/ibkr_symbols.yaml`. The rotation controller automatically respects the new dwell interval on the next run.
