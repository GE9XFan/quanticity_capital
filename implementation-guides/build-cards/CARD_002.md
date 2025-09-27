# BUILD CARD 002: AlphaVantage Option Chain Normalizer

**Difficulty:** ⭐⭐☆☆☆
**Time:** 5 hours
**Prerequisites:**
- CARD_001 complete (rate limiter available)
- Sample AlphaVantage option chain payloads captured and stored under `tests/fixtures/`
- DTO schema drafted in `contracts/v1.0.0/option_chain.yaml`

## Objective
Normalize AlphaVantage option chain responses into the internal `OptionQuote` DTO with consistent typing, timestamp handling, and error surfaces.

## Success Criteria
- [ ] Converts full chain + single contract responses into normalized DTOs
- [ ] Preserves bid/ask/last/volume/open_interest/greeks placeholders
- [ ] Rejects malformed payloads with typed exceptions
- [ ] Publishes normalized payload to `ingestion.quotes.alpha` topic/stream

## Implementation
1. Review `quantum-trading-architecture.md` Layer 1 responsibilities for required fields.
2. Extend `contracts/v1.0.0/option_chain.yaml` with field definitions (symbol, expiry, strike, option_type, greeks stub, timestamp).
3. Implement parser in `data_ingestion/alphavantage_normalizer.py` that accepts raw payloads and returns DTO objects/dataclasses.
4. Add schema validation using `pydantic` or custom validators to enforce typing and timestamp format.
5. Connect the normalizer to `alphavantage_client.py` so real-time streams emit standardized records.
6. Document serialization/transport details in `phase-1-data/layer-1-ingestion/alphavantage-setup.md`.

## Verification
- Run `pytest tests/layer1/test_option_normalizer.py`
- Execute integration check `python scripts/stream_alpha.py --symbol SPY --duration 60` verifying events appear on the ingestion topic with normalized fields.
- Capture sample event and compare against contract schema using `scripts/validate_contract.py option_chain:v1.0.0 sample.json`.

## Links to Next Cards
- [CARD_003](CARD_003.md): Redis TimeSeries Schema Definition
- CARD_004: IBKR Tick Stream Harmonization (TBD)
