# BUILD CARD 002: AlphaVantage Option Chain Normalizer

**Difficulty:** ⭐⭐⭐☆☆
**Time:** 6 hours
**Prerequisites:**
- [CARD_001](CARD_001.md) complete (client helpers returning raw payloads)
- Sample AlphaVantage option chain payloads captured under `tests/fixtures/alpha_vantage/`
- DTO schema `option_chain:v1.0.0` reviewed for completeness

## Objective
Transform AlphaVantage real-time and historical option chain payloads (with `requiredGreeks=true`) into the internal `OptionQuote` DTO, enforcing schema compliance, timestamp hygiene, and downstream transport expectations.

## Success Criteria
- [ ] Full-chain and single-contract responses convert into DTOs with Greeks populated when present, placeholders otherwise
- [ ] Historical fetch (`fetch_historical_chain`) normalizes each trade_date batch with correct session timezone handling
- [ ] Validation rejects malformed or stale records with typed exceptions (`OptionPayloadError`, `MissingGreeksError`)
- [ ] Normalized payloads publish to `ingestion.quotes.alpha` and `ingestion.quotes.alpha.historical` streams with metadata describing source and freshness

## Implementation
1. Implement `data_ingestion/alphavantage_normalizer.py` with functions `normalize_realtime_chain`, `normalize_historical_chain`, and `normalize_contract` that emit `OptionQuote` DTOs.
2. Map AlphaVantage Greeks fields (`impliedVolatility`, `delta`, `gamma`, `theta`, `vega`, `rho`) into DTO greeks, defaulting to `None` when the API omits values; annotate metadata with `greeks_source=alphavantage`.
3. Enforce timestamp parsing (`lastTradeDateTime`, `refreshTime`) into UTC ISO 8601 with millisecond precision; tag stale records (>2 minutes old) via `metadata.quality_flags`.
4. Integrate the normalizer into `AlphaVantageClient` by returning DTO lists instead of raw JSON, and expose generator helpers for streaming contexts.
5. Extend `scripts/stream_alpha.py` with a `--historical-date` and `--output-path` flag to capture normalized batches for validation.
6. Document failure handling and transport topics in `phase-1-data/layer-1-ingestion/alphavantage-setup.md` and link to relevant runbooks.

## Verification
- Unit tests: `pytest tests/layer1/test_option_normalizer.py`
- Contract validation: `scripts/validate_contract.py option_chain:v1.0.0 docs/evidence/phase1/sample_option_chain.json`
- Live replay: `python scripts/stream_alpha.py --symbol SPY --historical-date 2025-09-20 --output-path docs/evidence/phase1/option_chain_spy_2025-09-20.json`
- Observability: confirm `data_ingestion.normalizer.success_rate` metric exceeds 99% during live test window

## Links to Next Cards
- [CARD_005](CARD_005.md): Indicator & Intraday Cache Service
- [CARD_004](CARD_004.md): IBKR Tick Stream Harmonization
- [CARD_003](CARD_003.md): Redis TimeSeries Schema Definition (for storage integration)
