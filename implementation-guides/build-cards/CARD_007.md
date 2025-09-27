# BUILD CARD 007: Redis Bootstrap Script

**Difficulty:** ⭐⭐☆☆☆
**Time:** 3 hours
**Prerequisites:**
- Redis TimeSeries module deployed
- Contract `redis_timeseries_schema:v1.0.0`
- CARD_003 complete

## Objective
Create `scripts/bootstrap_redis_timeseries.py` to provision TimeSeries keys, labels, retention, and downsampling rules per contract, with audit and dry-run modes.

## Success Criteria
- [ ] Script creates missing keys/rules idempotently across environments
- [ ] `--dry-run` outputs planned changes without modifying Redis
- [ ] `--audit` compares existing keys against contract expectations and reports gaps
- [ ] Unit tests `pytest tests/layer2/test_redis_bootstrap.py` cover core functionality

## Implementation
1. Read schema definitions from `contracts/v1.0.0/redis_timeseries_schema.yaml`.
2. Connect to Redis using credentials from `config/storage.yaml`.
3. Implement create/update logic with retries and logging.
4. Provide CLI args: `--env`, `--dry-run`, `--audit`, `--apply`.
5. Document usage in `redis-timeseries.md` and `query-patterns.md`.

## Verification
- `pytest tests/layer2/test_redis_bootstrap.py`
- Run `python scripts/bootstrap_redis_timeseries.py --env dev --dry-run`
- Run `... --env dev --audit` to ensure no discrepancies post-apply

## Links to Next Cards
- [CARD_008](CARD_008.md): Backup Automation
- CARD_009: Query Helper API
