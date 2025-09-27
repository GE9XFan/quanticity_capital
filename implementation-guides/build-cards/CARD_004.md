# BUILD CARD 004: IBKR Tick Stream Harmonization

**Difficulty:** ⭐⭐⭐⭐☆
**Time:** 6 hours
**Prerequisites:**
- [CARD_000](CARD_000.md) environment baseline complete (IBKR gateway reachable)
- [CARD_001](CARD_001.md) and [CARD_002](CARD_002.md) complete (AlphaVantage DTOs available for cross-checks)
- Access to IBKR paper trading environment with target symbol permissions
- Contract schemas `option_chain:v1.0.0` and `market_data:v1.0.0`

## Objective
Normalize IBKR tick, depth, and reference data into unified DTOs (`UnderlyingQuote`, `TickEvent`, `OrderBookSnapshot`) and publish them alongside AlphaVantage data so downstream consumers can reconcile feeds with consistent timestamps and quality flags.

## Success Criteria
- [ ] `reqMktData`, `reqTickByTickData`, and `reqMarketDepth` streams emit DTOs with exchange timestamps aligned to UTC within ±100 ms of AlphaVantage spot data
- [ ] Contract metadata validated against `option_chain:v1.0.0` and discrepancies logged with remediation notes
- [ ] Live integration test `pytest tests/live/test_ibkr_live.py::test_tick_stream` passes when IBKR creds configured
- [ ] Streaming smoke test `python scripts/stream_ibkr.py --symbol SPY --duration 180 --compare-alpha` generates reconciliation report stored in `docs/evidence/phase1/ibkr_vs_alpha.json`

## Implementation
1. Implement DTO definitions in `data_ingestion/dto.py` (or update existing module) covering underlying quotes, tick events, and DOM snapshots.
2. Extend `IBKRClient` (using `ib_async`/`ib_insync` patterns) to expose async generators for L1 quotes, tick-by-tick, and depth updates with automatic reconnection.
3. Map raw events to DTOs, including exchange timestamps, market data type, and quality flags; attach `source="ibkr"` metadata for reconciliation.
4. Publish events to `ingestion.quotes.ibkr` and `ingestion.refdata.ibkr` streams; if AlphaVantage parity check fails, emit warning metric `data_ingestion.ibkr.alpha_diff`.
5. Document configuration toggles (client IDs, host/port, market data type) and reconciliation workflow in `ibkr-integration.md`.

## Verification
- Unit test suite: `pytest tests/layer1/test_ibkr_wrapper.py`
- Live parity smoke: `python scripts/stream_ibkr.py --symbol SPY --duration 180 --compare-alpha`
- Contract validation: `scripts/validate_contract.py option_chain:v1.0.0 docs/evidence/phase1/ibkr_option_chain_sample.json`
- Grafana: confirm `data_ingestion.ibkr.disconnects` and `data_ingestion.ibkr.alpha_diff` panels remain green during test window

## Links to Next Cards
- [CARD_006](CARD_006.md): Ingestion Monitoring & Observability Wiring
- [CARD_003](CARD_003.md): Redis TimeSeries Schema Definition (for unified storage)
