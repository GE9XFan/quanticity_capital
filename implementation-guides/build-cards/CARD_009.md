# BUILD CARD 009: Query Helper API

**Difficulty:** ⭐⭐☆☆☆
**Time:** 3 hours
**Prerequisites:**
- CARD_003 and CARD_007 complete
- Contracts `redis_timeseries_schema:v1.0.0` and downstream analytics requirements

## Objective
Expose a Python helper module `storage/query_helpers.py` that standardizes Redis TimeSeries access patterns for analytics and reporting layers.

## Success Criteria
- [ ] Helper provides functions for latest value, ranged queries, and multi-series fetches
- [ ] Enforces contract-compliant key construction
- [ ] Unit tests `pytest tests/layer2/test_query_helpers.py` cover key scenarios
- [ ] Documentation in `query-patterns.md` updated with usage examples

## Implementation
1. Implement helper functions `get_latest`, `get_range`, `multi_range` using redis-py client.
2. Add caching or pagination as required for large datasets.
3. Provide configuration options for environment and retry policies.
4. Include logging and metrics for query latency.

## Verification
- `pytest tests/layer2/test_query_helpers.py`
- Execute sample script `python scripts/query_sample.py --symbol SPY --metric option_chain`
- Validate dashboard integration by pointing analytics module to new helpers.

## Links to Next Cards
- CARD_011 (future): Analytics Feature Store Loader
- CARD_012 (future): Reporting Data Extract Service
