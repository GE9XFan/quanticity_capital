# BUILD CARD 003: Redis TimeSeries Schema Definition

**Difficulty:** ⭐⭐☆☆☆
**Time:** 3 hours
**Prerequisites:**
- Redis Stack deployed with RedisTimeSeries module enabled
- Contracts for `OptionQuote` and `IndicatorSeries` finalized
- Access to observability stack for monitoring metrics

## Objective
Design and implement the Redis TimeSeries key schema, compaction rules, and retention policies supporting ingestion and analytics consumers.

## Success Criteria
- [ ] Key naming convention documented and approved
- [ ] Downsampling rules configured (1s -> 1m -> 5m -> 1h -> 1d)
- [ ] Retention windows align with storage mandates (hot vs cold data)
- [ ] Query patterns documented for analytics layer (range, aggregation)

## Implementation
1. Draft the schema in `phase-1-data/layer-2-storage/redis-timeseries.md`, including key patterns, labels, and retention.
2. Create `storage/redis_timeseries.py` helpers for writing/upserting time series with automatic rule creation.
3. Define configuration parameters in `config/storage.yaml` (retention, chunk size, duplicate policy).
4. Implement bootstrap script `python scripts/bootstrap_redis_timeseries.py` to apply rules in dev/staging environments.
5. Update `contracts/v1.0.0/redis_timeseries_schema.yaml` with canonical key structure and data contract.

## Verification
- Run `pytest tests/layer2/test_redis_schema.py`
- Execute `scripts/bootstrap_redis_timeseries.py --dry-run` and review generated plan
- Validate downsampling via `redis-cli TS.RANGE` commands documented in `appendices/redis-commands.md`

## Links to Next Cards
- CARD_004: IBKR Tick Stream Harmonization (TBD)
- CARD_005: Analytics Feature Store Loader (TBD)
