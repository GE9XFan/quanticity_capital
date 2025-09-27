# BUILD CARD 005: Indicator & Intraday Cache Service

**Difficulty:** ⭐⭐⭐☆☆
**Time:** 6 hours
**Prerequisites:**
- [CARD_001](CARD_001.md) and [CARD_002](CARD_002.md) complete
- Redis cache namespace provisioned with TTL policies from `phase-1-data/layer-2-storage/redis-timeseries.md`
- Contract `technical_indicators:v1.0.0`

## Objective
Deliver a unified service that polls AlphaVantage technical indicators (MACD, VWAP, Bollinger Bands) and intraday OHLC data, normalizes the payloads, and caches them to avoid churn while providing consistent feeds for analytics and hedging checks.

## Success Criteria
- [ ] Cache miss kicks off indicator + intraday fetch, storing results with configurable TTL and refresh cadence
- [ ] Cached payloads conform to `technical_indicators` and `market_data` contracts, tagged with `source=alpha_vantage`
- [ ] Live validation script `python scripts/stream_alpha_indicators.py --symbol SPY --duration 120` emits cached outputs without breaching rate limits
- [ ] Metrics `data_ingestion.indicators.cache_hit_rate` > 85% and `data_ingestion.indicators.refresh_latency_ms` < 500 p95 during smoke

## Implementation
1. Create `data_ingestion/indicator_service.py` providing async helpers `get_indicators(symbol)` and `get_intraday(symbol, interval)` that rely on `AlphaVantageClient` to fetch raw data when cache TTL expires.
2. Store results in Redis using structured keys (`indicator:{symbol}:{indicator}` and `intraday:{symbol}:{interval}`) with TTL/refresh settings from config.
3. Publish normalized indicator series to event bus `ingestion.indicators.alpha` and intraday snapshots to `ingestion.marketdata.live` for downstream consumers.
4. Update `config/trading_params.yaml::alpha_vantage` with indicator refresh cadence, cache TTL, and intraday intervals, referencing `alphavantage-setup.md`.
5. Extend observability instrumentation to track cache hits/misses, refresh latency, and AlphaVantage call counts per indicator type.

## Verification
- Unit tests: `pytest tests/layer1/test_indicator_service.py`
- Live smoke: `python scripts/stream_alpha_indicators.py --symbol SPY --duration 120 --interval 1min`
- Contract validation: `scripts/validate_contract.py technical_indicators:v1.0.0 docs/evidence/phase1/sample_indicator_payload.json`
- Dashboard review: confirm indicator cache panels in Grafana ingestion overview reflect latest run

## Links to Next Cards
- [CARD_006](CARD_006.md): Ingestion Monitoring & Observability Wiring
- [CARD_003](CARD_003.md): Redis TimeSeries Schema Definition
- [CARD_007](CARD_007.md): Redis Bootstrap Script
