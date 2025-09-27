# Redis TimeSeries Schema & Setup

## Overview
Define the canonical Redis TimeSeries layout aligning with `contracts/v1.0.0/redis_timeseries_schema.yaml` and ensure ingestion pipelines automatically create required keys and rules.

## Setup Steps
1. Deploy Redis Stack (docker-compose or managed service) with RedisTimeSeries module enabled.
2. Configure connection details in `config/storage.yaml::redis.primary`.
3. Execute `scripts/bootstrap_redis_timeseries.py` to create TS keys, labels, and aggregation rules.
4. Verify key creation using commands in `appendices/redis-commands.md`.

## Key Pattern
```
{env}:{layer}:{symbol}:{metric}:{granularity}
```
- `env`: dev/staging/prod
- `layer`: ingestion/analytics/risk
- `symbol`: ticker or asset identifier
- `metric`: data stream name (option_chain, greeks, liquidity)
- `granularity`: 1s/1m/5m/1h/1d

## Aggregation Rules
| Source Granularity | Target | Aggregation | Bucket (ms) |
|--------------------|--------|-------------|-------------|
| 1s | 1m | AVG | 60000 |
| 1m | 5m | AVG | 300000 |
| 5m | 1h | AVG | 3600000 |
| 1h | 1d | AVG | 86400000 |

## Retention Policy
- 1s: 7 days
- 1m: 30 days
- 5m: 90 days
- 1h: 365 days
- 1d: 5 years (archived periodically to S3)

## Write API Guidelines
- Use `TS.ADD` with `ON_DUPLICATE LAST` to prevent backdated overwrites.
- Tag records with labels `env`, `layer`, `symbol`, `metric` for query filters.
- Batch pipeline writes to minimize latency (group by symbol + granularity).

## Monitoring
- Track `redis_ts.dirty_memory_ratio`, `redis_ts.command_latency`, `redis_ts.rules_pending`.
- Alert when retention gaps detected via audit script.

## Testing
- Run `pytest tests/layer2/test_redis_schema.py` after schema updates.
- Execute `scripts/bootstrap_redis_timeseries.py --dry-run` in CI to confirm idempotency.
