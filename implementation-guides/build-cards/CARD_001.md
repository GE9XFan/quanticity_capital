# BUILD CARD 001: AlphaVantage Rate Limiter

**Difficulty:** ⭐⭐⭐☆☆
**Time:** 4 hours
**Prerequisites:**
- Redis Stack running locally or in dev cluster
- Python 3.11 environment with `aioredis` client installed
- AlphaVantage premium API key stored in secrets manager

## Objective
Implement token-bucket rate limiting that guarantees the AlphaVantage adapter does not exceed 600 requests per minute across concurrent workers.

## Success Criteria
- [ ] p95 request rate stays below 600/minute under a 50 request burst
- [ ] Retry logic backs off and recovers after synthetic 429 responses
- [ ] Token bucket state persists across process restarts
- [ ] Metrics emitted to `data_ingestion.rate_limit.*`

## Implementation
1. Define the `rate_limit_config` contract in `contracts/v1.0.0/alphavantage_rate_limit.yaml` (or update existing schema).
2. Create `data_ingestion/rate_limit_controller.py` implementing a Redis-backed token bucket (use `SETNX` for lock, `PEXPIRE` for refill cadence).
3. Wire the controller into `alphavantage_client.py` so each API call requests a token before hitting the external service.
4. Implement jittered retry handling (50–150 ms) for HTTP 429 and network timeouts.
5. Expose metrics via your telemetry framework (e.g., `prometheus_client` gauges/counters) and document them in the layer guide.
6. Add configuration knobs to `config/trading_params.yaml` for requests-per-minute and burst size.

## Verification
- Run `pytest tests/layer1/test_rate_limiter.py` (to be created) ensuring all scenarios pass.
- Execute the stress script `python scripts/simulate_av_load.py --burst 50 --duration 120` and confirm logs show no limit breaches.
- Inspect observability dashboard for `data_ingestion.rate_limit.tokens_available` staying within expected bounds during the test.

## Links to Next Cards
- [CARD_002](CARD_002.md): AlphaVantage Option Chain Normalizer
- [CARD_003](CARD_003.md): Redis TimeSeries Schema Definition
