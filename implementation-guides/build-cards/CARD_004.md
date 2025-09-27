# BUILD CARD 004: IBKR Tick Stream Harmonization

**Difficulty:** ⭐⭐⭐⭐☆
**Time:** 6 hours
**Prerequisites:**
- CARD_001 and CARD_002 complete (rate limiter and option normalizer)
- Access to IBKR paper trading environment
- Contract schemas `option_chain:v1.0.0` and `market_data:v1.0.0`

## Objective
Normalize IBKR tick, depth, and reference data into unified DTOs (`UnderlyingQuote`, `TickEvent`, `OrderBookSnapshot`) and publish to ingestion topics.

## Success Criteria
- [ ] `reqMktData`, `reqTickByTickData`, and `reqMarketDepth` streams convert to DTOs with consistent timestamps
- [ ] Contract metadata validated against `option_chain:v1.0.0`
- [ ] Integration test `pytest tests/layer1/test_ibkr_wrapper.py` passes with simulated data
- [ ] Streaming smoke test `python scripts/stream_ibkr.py --symbol SPY --duration 120` emits normalized events

## Implementation
1. Implement DTO definitions in `data_ingestion/dto.py` (or update existing module).
2. Extend `IBKRClient` to expose async generators for L1 quotes, tick-by-tick, and DOM updates.
3. Map raw events to DTOs, including exchange timestamps and quality flags.
4. Publish events to `ingestion.quotes.ibkr` and `ingestion.refdata.ibkr` topics/streams.
5. Document configuration toggles and contract mappings in `ibkr-integration.md`.

## Verification
- `pytest tests/layer1/test_ibkr_wrapper.py`
- Manual smoke test `python scripts/stream_ibkr.py --symbol SPY --duration 120`
- Schema check `scripts/validate_contract.py option_chain:v1.0.0 samples/ibkr_option_chain.json`

## Links to Next Cards
- [CARD_006](CARD_006.md): Ingestion Monitoring & Observability Wiring
- CARD_008: Backup Automation for Redis TimeSeries (after storage layer complete)
