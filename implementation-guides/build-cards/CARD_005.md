# BUILD CARD 005: Indicator Cache Service

**Difficulty:** ⭐⭐⭐☆☆
**Time:** 5 hours
**Prerequisites:**
- CARD_001 and CARD_002 complete (rate limiter + normalizer)
- Redis cache namespace provisioned
- Contract `technical_indicators:v1.0.0`

## Objective
Implement caching layer for AlphaVantage technical indicators (MACD, VWAP, Bollinger Bands) to avoid redundant API calls and provide consistent data to analytics.

## Success Criteria
- [ ] Cached responses keyed by symbol + indicator persist for configurable TTL
- [ ] Cache miss triggers API call, hit returns stored payload within <5 ms
- [ ] Indicator payloads validated against `technical_indicators:v1.0.0`
- [ ] Unit test `pytest tests/layer1/test_indicator_cache.py` covers TTL & invalidation

## Implementation
1. Develop `data_ingestion/indicator_cache.py` with Redis backend and serialization helpers.
2. Integrate cache with `alphavantage_client.py` to populate before publishing events.
3. Add configuration entries in `config/trading_params.yaml::alpha_vantage.indicator_cache` (TTL, namespace, refresh cadence).
4. Instrument metrics `data_ingestion.indicators.cache_hit_rate` and `...miss_count`.
5. Update documentation in `alphavantage-setup.md` and `rate-limiting.md` with cache references.

## Verification
- `pytest tests/layer1/test_indicator_cache.py`
- Script `python scripts/simulate_indicator_cache.py --symbol SPY --loops 100` (stub)
- Dashboard segment `analytics.grafana/indicator_cache` shows hit rate >85%

## Links to Next Cards
- [CARD_006](CARD_006.md): Ingestion Monitoring & Observability Wiring
- CARD_007: Redis Bootstrap Script
