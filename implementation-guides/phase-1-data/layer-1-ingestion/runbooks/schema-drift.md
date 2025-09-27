# Runbook: Schema Drift Response

## Purpose
Handle upstream payload changes that break contract compliance for AlphaVantage or IBKR streams.

## Detection
- Contract validation failure alert from `scripts/validate_contract.py` in CI.
- Runtime exception `SchemaValidationError` in ingestion logs.
- Monitoring alert `data_ingestion.schema_drift_detected = 1`.

## Preconditions
- Access to failing payload samples stored in `phase-1-data/layer-1-ingestion/schemas/`.
- Ability to patch ingestion normalization code.
- Coordination with downstream teams (analytics, storage).

## Response Steps
1. **Quarantine Bad Payloads**
   - Enable quarantine mode via feature flag `config/trading_params.yaml::ingestion.quarantine = true`.
   - Redirect invalid events to `ingestion.quarantine` stream for analysis.
2. **Collect Samples**
   - Save at least 10 failing payloads into `schemas/anomalies/{timestamp}.json`.
   - Run `scripts/validate_contract.py option_chain:v1.0.0 schemas/anomalies/sample.json` to confirm failure mode.
3. **Assess Contract Impact**
   - Compare new payload fields with contract definitions.
   - If breaking change required, draft update to relevant contract file and bump version (e.g., `option_chain:v1.1.0`).
4. **Coordinate Downstream Consumers**
   - Notify analytics, storage, and AI teams of proposed changes.
   - Update `dependencies.lock` with impacted layers.
5. **Implement Fix**
   - Update normalizer code and associated tests (`tests/layer1/test_option_normalizer.py`).
   - Validate using sample payloads.
6. **Deploy Hotfix**
   - Roll out updated service in staging, run regression tests.
   - Promote to production after sign-off.
7. **Monitor**
   - Observe schema validation metrics for 1 hour.
   - Ensure no downstream alerts triggered.

## Post-Recovery Actions
- Update contract version history with new version and summary.
- Document incident in knowledge base revision history.
- Schedule review to prevent recurrence.

## Links
- Build Cards: `CARD_002`, `CARD_005`
- Contracts: All ingestion-related contracts (`option_chain`, `market_data`, `technical_indicators`)
- Tests: `tests/layer1/test_option_normalizer.py`, `tests/layer3/test_indicator_cache.py`
