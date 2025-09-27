# Redis TimeSeries Command Reference

Use these commands when validating schema, retention, and compaction rules documented in `contracts/v1.0.0/redis_timeseries_schema.yaml`.

## Inspect Series Metadata
```bash
redis-cli TS.INFO dev:ingestion:SPY:option_chain:1s
```

## Query Raw Series
```bash
redis-cli TS.RANGE dev:ingestion:SPY:option_chain:1s - + COUNT 5
```

## Query Aggregated Series
```bash
redis-cli TS.RANGE dev:analytics:SPY:greeks:1m - + AGGREGATION avg 60000
```

## List Matching Keys
```bash
redis-cli KEYS dev:ingestion:SPY:*
```

## Create Downsampling Rule Manually
```bash
redis-cli TS.CREATERULE dev:ingestion:SPY:option_chain:1s dev:ingestion:SPY:option_chain:1m AVG 60000
```

## Validate Retention Settings
```bash
redis-cli TS.INFO dev:ingestion:SPY:option_chain:1s | grep retention
```

## Remove Rule (Use with Caution)
```bash
redis-cli TS.DELETERULE dev:ingestion:SPY:option_chain:1s dev:ingestion:SPY:option_chain:1m
```

## Notes
- Always execute commands in `--raw` mode if you need machine-friendly output for scripts.
- For production environments, prefer using the bootstrap script documented in CARD_003 instead of manual commands.
