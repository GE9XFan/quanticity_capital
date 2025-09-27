# AlphaVantage Setup

## Purpose
Configure and validate the AlphaVantage premium integration for options, intraday spot data, and technical indicators as described in `quantum-trading-architecture.md` Layer 1.

## Prerequisites
- AlphaVantage premium API key stored in vault and referenced via environment variable `ALPHAVANTAGE_API_KEY`.
- Python environment with `alpha_vantage==2.3.1` installed.
- Redis endpoint reachable for rate limiting cache.
- Configuration file `config/trading_params.yaml::alpha_vantage` present.

## Installation Steps
1. Install dependencies:
   ```bash
   pip install alpha_vantage==2.3.1 tenacity aiohttp
   ```
2. Create wrapper module `data_ingestion/alphavantage_client.py` using recommended patterns from architecture doc.
3. Load API key from secrets manager and inject via dependency container or environment.
4. Configure rate limit parameters referencing `contracts/v1.0.0/alphavantage_rate_limit.yaml`.
5. Set up caching for technical indicator results (`IndicatorSeries`) to avoid redundant API calls.

## Configuration Mapping
| Parameter | Location | Notes |
|-----------|----------|-------|
| `symbols` | `config/trading_params.yaml::alpha_vantage.symbols` | Watchlist with DTE buckets |
| `rate_limit` | `config/trading_params.yaml::alpha_vantage.rate_limit` | Must match contract schema |
| `indicators` | `config/trading_params.yaml::alpha_vantage.indicators` | Toggle VWAP, MACD, BBands |
| `retry_policy` | `config/trading_params.yaml::alpha_vantage.retry` | Jitter bounds 50–150 ms |

## Testing Checklist
- [ ] Run `pytest tests/layer1/test_alphavantage_client.py`
- [ ] Execute `python scripts/stream_alpha.py --symbol SPY --duration 60` and confirm normalized events published
- [ ] Validate schema compliance: `scripts/validate_contract.py option_chain:v1.0.0 samples/option_chain.json`
- [ ] Monitor `data_ingestion.alpha_vantage.latency_ms` metric for p95 < 300ms

## Troubleshooting
- Missing data fields: verify AlphaVantage entitlement tier.
- Frequent throttling: adjust burst size in `alphavantage_rate_limit` and investigate concurrency.
- Indicator cache misses: ensure Redis namespace matches configuration.
