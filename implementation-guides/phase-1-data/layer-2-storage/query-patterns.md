# Query Patterns

## Purpose
Enumerate standard Redis TimeSeries queries used by analytics, signals, and reporting layers to ensure consistent access patterns.

## Common Queries
### Latest Quote Snapshot
```bash
redis-cli TS.GET prod:ingestion:SPY:option_chain:1s
```

### Time-Weighted Average Greeks
```bash
redis-cli TS.RANGE prod:analytics:SPY:greeks:1m - + AGGREGATION avg 300000
```

### Liquidity Stress Range Query
```bash
redis-cli TS.MRANGE - + FILTER metric=liquidity_stress symbol=SPY
```

### Backfill for Backtests
Use helper in `storage/data_persistence.py`:
```python
fetch_timeseries(symbol="SPY", metric="option_chain", start="-7d", end="now", granularity="1m")
```

## Performance Tips
- Prefer `TS.MRANGE` with LABEL filters for multi-series queries.
- Use `COUNT` to cap result size for UI dashboards.
- Cache high-frequency queries in application layer when dashboards poll frequently.

## Access Controls
- Restrict write access to ingestion services; analytics operates read-only.
- Audit queries via Redis ACL logging where available.

## Open Items
- Define standardized Python helper wrappers for analytics modules (CARD_007).
- Evaluate need for data lake export for long-term analytics beyond 5-year retention.
