# Layer 1: Data Ingestion Implementation Guide

## Status Dashboard
```yaml
status: PLANNING
completion: 0
blockers: []
last_updated: 2025-09-27
owner: Michael Merrick
```

## Implementation Tracker
- [ ] Structure defined
- [ ] Contracts documented
- [ ] Core code complete
- [ ] Integration tests
- [ ] 30-day stability run
- [ ] Production handoff

---

## 1. Mission & Scope
- **Objective:** Deliver resilient AlphaVantage and IBKR market data ingestion covering 0DTE, 1DTE, and 14+ DTE options, normalized for downstream analytics.
- **In Scope:** API client wrappers, rate limiting, normalization, resiliency, observability.
- **Out of Scope:** Storage retention enforcement (deferred to Layer 2), signal computations.

## 2. Source Architecture Alignment
- Architecture reference: `quantum-trading-architecture.md:81`
- Key capabilities: premium AlphaVantage integration, concurrency-aware rate limiting, IBKR real-time feeds, DTO normalization, observability hooks.

## 3. Preconditions & Environment
- Phase 0 environment baseline complete with evidence in `docs/evidence/phase0/`.
- Redis Stack with TimeSeries module available for rate limiter state.
- AlphaVantage premium credentials stored in secret manager.
- IBKR TWS/Gateway sandbox or paper account accessible.
- Python 3.11 runtime with `alpha_vantage`, `ib_async`, `pydantic`, `redis` libs.

## 4. Dependencies & Contracts
- Upstream: None (source layer).
- Downstream: Layer 2 storage, Layer 3 analytics, Layer 7 AI overseer.
- Contracts: `option_chain:v1.0.0`, `market_data:v1.0.0`, `technical_indicators:v1.0.0`, `alphavantage_rate_limit:v1.0.0`.
- Changes tracked via `dependencies.lock` entry `layer_1_data_ingestion`.

## 5. Implementation Plan
- CARD_000 – Complete Phase 0 environment baseline before starting ingestion work.
- CARD_001 – AlphaVantage Client Integration (real-time, historical, intraday helpers).
- CARD_002 – Option Chain Normalizer (DTO + validation, Greeks handling).
- CARD_004 – IBKR Tick Stream Harmonization (live + historical tick parity).
- CARD_005 – Indicator & Intraday Cache Service (BBands, VWAP, MACD delivery).
- CARD_006 – Ingestion Monitoring & Observability Wiring.
- CARD_003 – Redis TimeSeries Schema Definition (hand-off to storage team).

## 6. Detailed Procedures
- See `alphavantage-setup.md` for AlphaVantage client initialization and configuration contracts.
- Consult `time-series-intraday.md` for intraday polling cadence, indicator refresh, and cache wiring.
- Use `ibkr-integration.md` for IBKR session management and streaming patterns.
- Rate limiting and retries covered in `rate-limiting.md`.
- Failure handling captured in `error-recovery.md` and runbooks.

## 7. Resilience & Observability
- Instrument metrics `data_ingestion.rate_limit.*`, `data_ingestion.alphavantage.latency_ms`, `data_ingestion.ibkr.disconnects`, `data_ingestion.indicators.cache_hit_rate`, `data_ingestion.indicators.refresh_latency_ms`.
- Alert thresholds defined in `appendices/monitoring-guide.md`.
- Mirror raw ticks to append-only storage for audit compliance.

## 8. Testing & Validation
- Unit tests under `tests/` directory (e.g., `test_alphavantage_client.py`, `test_option_normalizer.py`, `test_indicator_service.py`).
- Live API validation via `pytest tests/live/test_alpha_vantage_live.py` (skips when creds absent) and `scripts/stream_alpha.py` / `scripts/stream_alpha_indicators.py`.
- IBKR parity testing with `scripts/stream_ibkr.py` to compare against AlphaVantage spot/option data.
- Load testing using `scripts/simulate_av_load.py` once rate limiter and cache are in place.

## 9. Runbooks & Operations
- Draft runbooks in `runbooks/` (reconnect procedures, credential rotation, failover steps).
- Include escalation matrix referencing `timeline.yaml` owners.

## 10. Compliance & Audit
- Log AlphaVantage and IBKR error codes for review.
- Retain raw payloads for 90 days in cold storage.
- Ensure API key usage aligns with vendor agreements.

## 11. Open Questions & Risks
- Pending IBKR API approval for production market data.
- Need decision on shared vs per-service Redis namespace.

## 12. Revision History
| Date       | Author | Change Summary |
|------------|--------|----------------|
| 2025-09-27 | Michael Merrick | Rebase Phase 1 plan, added Phase 0 prerequisites, live API validation |
| 2024-10-07 | TBA    | Initial scaffold |
