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
