# BUILD CARD 001: AlphaVantage Client Integration

**Difficulty:** ⭐⭐⭐⭐☆
**Time:** 8 hours
**Prerequisites:**
- CARD_000 complete with live check scripts verified
- Contracts `option_chain:v1.0.0`, `market_data:v1.0.0`, `technical_indicators:v1.0.0`
- Phase 1 config stubs present in `config/trading_params.yaml`

## Objective
Wrap the official `alpha_vantage` library into `data_ingestion/alphavantage_client.py`, exposing helpers for real-time options (`requiredGreeks=true`), historical chain by date, and intraday time-series for the underlying, matching architecture requirements without re-implementing vendor logic.

## Success Criteria
- [ ] `AlphaVantageClient.fetch_realtime_chain(symbol, required_greeks=True)` returns full chain payloads normalized into DTOs
- [ ] `AlphaVantageClient.fetch_historical_chain(symbol, trade_date)` iterates specific dates without exceeding vendor pagination limits
- [ ] `AlphaVantageClient.fetch_intraday(symbol, interval)` delivers OHLC/VWAP snapshots needed for hedging validation
- [ ] Rate limiter metrics (`data_ingestion.rate_limit.tokens_available`) stay within bounds during 120s live smoke
- [ ] Live API integration test `pytest tests/live/test_alpha_vantage_live.py::test_realtime_chain` passes when `ALPHAVANTAGE_API_KEY` is set

## Implementation
1. Scaffold `data_ingestion/alphavantage_client.py` using the reference patterns from the upstream repository (do **not** fork core client code).
2. Implement async wrappers around `Options.get_realtime_options`, `Options.get_historical_options`, and `TimeSeries.get_intraday` with `run_in_executor` so concurrency matches architecture guidance.
3. Wrap every outbound call with the Redis-backed `RateLimitController` described in `rate-limiting.md`, ensuring concurrency budgets stay within 600 requests/minute.
4. Ensure real-time calls always pass `requiredGreeks=True` and map returned Greeks into the DTO placeholders (delta, gamma, vega, theta, rho).
5. Provide a `fetch_historical_chain(symbol, *, from_date, to_date=None)` helper that iterates per-day requests and yields normalized batches, enforcing the AlphaVantage date parameter contract.
6. Normalize intraday time series into the `market_data` contract structure, computing derived VWAP locally when missing and tagging `quality_flags` accordingly.
7. Surface retry configuration (jitter, max_attempts) and symbol buckets (0DTE, 1DTE, 14-45DTE) through `config/trading_params.yaml` entries documented in `phase-1-data/layer-1-ingestion/alphavantage-setup.md`.
8. Capture live sample payloads in `tests/fixtures/alpha_vantage/` for regression tests, redacting API keys before committing.

## Verification
- Run unit tests: `pytest tests/layer1/test_alphavantage_client.py`
- Run live smoke: `pytest tests/live/test_alpha_vantage_live.py --symbol SPY --dte-buckets 0 1 21` (skipped automatically when API key absent)
- Execute `python scripts/stream_alpha.py --symbol SPY --duration 120 --required-greeks true` and archive the output JSON to `docs/evidence/phase1/alpha_vantage_stream.json`
- Record Grafana chart showing `alphavantage.latency_ms` and `alphavantage.calls_remaining` during the smoke test

## Links to Next Cards
- [CARD_002](CARD_002.md): AlphaVantage Option Chain Normalizer
- [CARD_004](CARD_004.md): IBKR Tick Stream Harmonization
- [CARD_005](CARD_005.md): Indicator & Intraday Cache Service
