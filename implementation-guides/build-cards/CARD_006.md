# BUILD CARD 006: Ingestion Monitoring & Observability Wiring

**Difficulty:** ⭐⭐⭐☆☆
**Time:** 4 hours
**Prerequisites:**
- Metrics backend (Prometheus/Grafana) available
- CARD_001 through CARD_005 completed
- Monitoring guide `appendices/monitoring-guide.md`

## Objective
Instrument Layer 1 ingestion with metrics, logs, and alerts aligned to the Monitoring Guide, ensuring dashboards surface key health signals.

## Success Criteria
- [ ] Metrics emitted: `data_ingestion.rate_limit.*`, `data_ingestion.alpha_vantage.latency_ms`, `data_ingestion.ibkr.disconnects`
- [ ] Alerts configured with runbook links for AlphaVantage outage and IBKR reconnect
- [ ] Dashboard panels created/updated in `analytics.grafana/ingestion_overview`
- [ ] Test `pytest tests/layer1/test_stream_health_checks.py` validates heartbeat instrumentation

## Implementation
1. Add metrics instrumentation in ingestion services using chosen telemetry SDK.
2. Define alert rules referencing runbooks (`alphavantage-outage.md`, `ibkr-reconnect.md`).
3. Update Grafana dashboard JSON and store snapshot in `dashboards/ingestion_overview.json` (stub).
4. Document monitoring endpoints in `rate-limiting.md` and `ibkr-integration.md`.

## Verification
- Run `pytest tests/layer1/test_stream_health_checks.py`
- Execute `scripts/stream_alpha.py` and `scripts/stream_ibkr.py` while observing dashboards
- Confirm alert firing in test mode and link to runbooks

## Links to Next Cards
- [CARD_007](CARD_007.md): Redis Bootstrap Script
- CARD_009: Query Helper API
