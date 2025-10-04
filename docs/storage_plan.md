# Storage Plan – Unusual Whales REST Snapshots

Phase 1 adds Redis snapshots on top of the existing disk archive so we always know the latest payload for each endpoint without digging through files.

## Destinations

| Endpoint Type | Redis Key | Fields | Notes |
|---------------|-----------|--------|-------|
| Global (no ticker) | `uw:rest:<endpoint>` | `payload` (JSON string), `fetched_at` (UTC ISO) | Key overwrites on every successful fetch. |
| Ticker-specific | `uw:rest:<endpoint>:<symbol>` | Same as above | One hash per symbol; overwritten each run. |

- **Disk Archive**: Continues to store every response under `data/unusual_whales/raw/<endpoint>/...` with metadata and an `index.ndjson` tracker. This remains the long-term audit trail.
- **Redis TTL**: None. Snapshots persist until overwritten by the next successful fetch.
- **Errors**: If a Redis write fails, the run logs an error but does not abort (disk copy is still authoritative).

## Flow Summary

1. Fetch endpoint via `httpx`.
2. Write raw JSON + metadata to disk (unchanged from Phase 0).
3. If `STORE_TO_REDIS=true`, serialise the JSON and upsert it into the appropriate Redis hash.

## Which feeds may need more than a snapshot?

Think of the table below as a sticky note for future phases. “Snapshot” means the Redis hash + disk files we already have are enough. “History later” means we expect to store older points (probably in Postgres or a Redis stream) once analytics are ready.

| Endpoint Family | Why we pull it | Do we need history? | Simple next step |
|-----------------|----------------|---------------------|------------------|
| `economic_calendar`, `market_*` globals | Market colour for dashboards | Snapshot only for now | Keep latest in Redis, exports later if charts are needed |
| `darkpool`, `flow_per_expiry`, `greek_exposure*`, `spot_exposures*`, `stock_state`, `stock_volume_price_levels` | Latest positioning data | Snapshot fine today | Revisit when analytics ask for deltas |
| `flow_alerts`, `net_prem_ticks`, `nope`, `ohlc_1m`, `options_volume` | Time series driving signals | **History later** (need trends) | Decision: capture every pull in a `uw_rest_*` Postgres table (partitioned by day) and keep a short Redis stream (maxlen ≈ 5k) for quick lookbacks. Work begins in Phase 2. |
| `option_chains`, `option_stock_price_levels`, `interpolated_iv`, `iv_rank`, `volatility_term_structure`, `max_pain` | Heavy payloads, usually viewed as a whole | Snapshot only, avoid bloating Redis | Leave in Redis hash + disk; parse on demand |

Nothing changes in code today—the table just keeps us honest about what to build when analytics arrive.

For the feeds marked **History later**, the plan is:

1. Append every REST pull into a dedicated Postgres table (one table per family) so analysts can query weeks or months of data.
2. Maintain a capped Redis stream (e.g. `uw:rest:flow_alerts:SPY:stream`, `maxlen` ≈ 5,000) for quick intraday lookbacks without hitting Postgres.
3. Keep the existing disk archive as the ultimate audit log.

We will wire this up in Phase 2 once the schema is finalised.

## Monitoring

- List keys created during the run:

  ```bash
  redis-cli KEYS 'uw:rest:*'
  ```

- Inspect a global endpoint snapshot:

  ```bash
  redis-cli HGETALL uw:rest:market_tide
  ```

- Inspect a ticker-specific snapshot:

  ```bash
  redis-cli HGETALL uw:rest:flow_alerts:SPY
  ```

- Tailing logs for Redis status:

  ```bash
  tail -f "$(ls -t logs/unusual_whales_rest_*.log | head -n 1)"
  ```

## Future Extensions (Deferred)

- Streams or historical storage in Redis/Postgres (not included in this phase).
- Derived metrics or parsed columns – snapshots remain raw JSON until analytics phases begin.
