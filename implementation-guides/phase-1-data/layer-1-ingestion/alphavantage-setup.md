# AlphaVantage Setup

## Purpose
Configure and validate the AlphaVantage premium integration for options, intraday spot data, and technical indicators exactly as prescribed in `quantum-trading-architecture.md` Layer 1. This guide aligns the implementation with the vetted upstream library so we reuse existing capability instead of rebuilding clients.

## Prerequisites
- Phase 0 environment baseline (`CARD_000`) completed with live connectivity verified.
- AlphaVantage premium API key stored in vault and exported to the runtime as `ALPHAVANTAGE_API_KEY`.
- Python 3.11 environment with `alpha_vantage==2.3.1`, `tenacity`, and `aiohttp` installed.
- Redis endpoint reachable for rate limiting, indicator caching, and intraday checkpoints.
- Configuration file `config/trading_params.yaml::alpha_vantage` present and tracked in version control (do not commit secrets).

## Installation Steps
1. Install dependencies:
   ```bash
   pip install alpha_vantage==2.3.1 tenacity aiohttp
   ```
2. Scaffold `data_ingestion/alphavantage_client.py` using the upstream `alpha_vantage` package (wrap the official client, no vendored code).
3. Load the API key from the secrets manager and inject via dependency container or environment variables.
4. Configure rate limit parameters referencing `contracts/v1.0.0/alphavantage_rate_limit.yaml` and store configuration in `config/trading_params.yaml`.
5. Implement indicator and intraday caching helpers per `CARD_005`, wiring Redis namespaces and TTLs.

## API Usage Patterns
### Real-Time Options
- Call `Options.get_realtime_options(symbol=symbol, call_put='ALL', strike=None, range='ALL', requiredGreeks=True)`.
- Always pass `requiredGreeks=True`; map returned Greeks fields into DTO placeholders and set `metadata.greeks_source="alphavantage"`.
- Capture request metadata (latency, call count) for observability and quota tracking.

### Historical Options
- Use `Options.get_historical_options(symbol, expiration, date=YYYY-MM-DD)` for specific trade dates.
- Expose `AlphaVantageClient.fetch_historical_chain(symbol, *, from_date, to_date=None)` that iterates date ranges day-by-day, respecting AlphaVantage pagination.
- Persist raw payloads to `data/raw/alphavantage/{symbol}/{date}.json` for replay and attach normalized outputs to `docs/evidence/phase1/`.

### Intraday Spot Data
- Invoke `TimeSeries.get_intraday(symbol=symbol, interval='1min', outputsize='full', datatype='json')` from an executor to avoid blocking the event loop.
- Normalize to the `market_data` contract, computing VWAP locally when AlphaVantage omits it and tagging `quality_flags` with `VWAP_RECOMPUTED`.

### Technical Indicators
- Poll `TechIndicators.get_macd`, `get_vwap`, and `get_bbands` per `time-series-intraday.md` cadence guidance.
- Reuse cached intraday prices when constructing payloads to minimize additional API calls.
- Publish normalized series to `ingestion.indicators.alpha` after validation.

## Configuration Mapping
| Parameter                | Location                                             | Notes |
|--------------------------|-------------------------------------------------------|-------|
| `symbols`                | `config/trading_params.yaml::alpha_vantage.symbols`   | Watchlist with DTE buckets (0, 1, 14-45) |
| `rate_limit`             | `config.trading_params.yaml::alpha_vantage.rate_limit`| Must match `alphavantage_rate_limit` contract |
| `retry_policy`           | `config.trading_params.yaml::alpha_vantage.retry`     | Configure jitter (50–150 ms) and max attempts |
| `historical.window_days` | `config.trading_params.yaml::alpha_vantage.historical`| Controls backfill range per run |
| `intraday.intervals`     | `config.trading_params.yaml::alpha_vantage.intraday`  | List of intervals (e.g., `['1min','5min']`) |
| `indicators.enabled`     | `config.trading_params.yaml::alpha_vantage.indicators`| Toggle MACD, VWAP, BBands |
| `cache.ttl_seconds`      | `config.trading_params.yaml::alpha_vantage.cache`     | TTL for indicator/intraday cache keys |

## Live Validation Workflow
1. Run unit tests: `pytest tests/layer1/test_alphavantage_client.py` and `pytest tests/layer1/test_option_normalizer.py`.
2. Execute live smoke: `pytest tests/live/test_alpha_vantage_live.py --symbol SPY --dte-buckets 0 1 21` (skips automatically if API key missing).
3. Stream data for manual inspection:
   ```bash
   python scripts/stream_alpha.py --symbol SPY --duration 180 --required-greeks true --output-path docs/evidence/phase1/spy_realtime.json
   python scripts/stream_alpha.py --symbol SPY --historical-date 2025-09-20 --output-path docs/evidence/phase1/spy_2025-09-20.json
   python scripts/stream_alpha_indicators.py --symbol SPY --duration 180 --interval 1min
   ```
4. Validate payloads against contracts:
   ```bash
   scripts/validate_contract.py option_chain:v1.0.0 docs/evidence/phase1/spy_realtime.json
   scripts/validate_contract.py technical_indicators:v1.0.0 docs/evidence/phase1/sample_indicator_payload.json
   ```
5. Monitor Grafana panel `Ingestion › AlphaVantage Latency` to confirm p95 < 300 ms and quota headroom.

## Troubleshooting
- **Missing Greeks:** ensure `requiredGreeks=True` and symbol entitlements cover the requested expiry; log incident in `runbooks/alpha_vantage_greeks.md`.
- **Frequent throttling:** adjust `requests_per_minute` and `burst_size` in config; verify `RateLimitController` metrics.
- **Indicator cache misses:** confirm Redis namespaces match configuration and TTL > refresh cadence.
- **Historical gaps:** rerun `fetch_historical_chain` with targeted date range and archive raw payloads for audit.

## Documentation & Evidence
- Update `docs/evidence/phase1/` with live outputs, metrics screenshots, and validation logs.
- Record configuration changes in `dependencies.lock` under `layer_1_data_ingestion` when contracts or downstream consumers change.
