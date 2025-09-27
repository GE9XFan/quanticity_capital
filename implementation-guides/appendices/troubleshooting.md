# Troubleshooting Playbook

Refer to this guide when diagnosing common issues during implementation or operations.

## Data Ingestion
- **Symptom:** AlphaVantage 429 errors.
  - Check `data_ingestion.rate_limit.tokens_available` metric.
  - Validate `alphavantage_rate_limit` config matches contract.
  - Inspect Redis bucket keys for stale counters; flush only with lead approval.
- **Symptom:** IBKR connection drops.
  - Review heartbeat logs in `logs/ibkr/`.
  - Confirm client IDs unique across services.
  - Execute runbook in `phase-1-data/layer-1-ingestion/runbooks/ibkr-reconnect.md` (to be authored).

## Storage
- **Symptom:** Missing TimeSeries keys.
  - Run `scripts/bootstrap_redis_timeseries.py --audit` to compare expected vs actual keys.
  - Verify retention settings in `config/storage.yaml` align with contract.
- **Symptom:** Compaction gaps.
  - Inspect Redis `TS.INFO` for `rules` mismatch.
  - Check background worker logs for failed pipeline operations.

## Analytics
- **Symptom:** Greeks latency regressions.
  - Enable detailed timing logs in `analytics/greeks_engine.py`.
  - Confirm Numba acceleration toggles in config.
  - Verify queue backlog length in message bus.
- **Symptom:** Regime classifier drift warnings.
  - Ensure feature inputs (liquidity, VPIN, macro) are up to date.
  - Review model retraining cron status in scheduler logs.

## Execution & Risk
- **Symptom:** Order rejections with code 10147.
  - Inspect pacing guard settings in `config/execution.yaml`.
  - Audit pending orders queue for stuck submissions.
- **Symptom:** Position mismatch after restart.
  - Trigger reconciliation script and compare with IBKR Flex report.
  - Review ledger replay logs for errors.

## AI & Reporting
- **Symptom:** AI decision SLA breach.
  - Check API quotas and latency metrics.
  - Review prompt size and tool invocation counts.
- **Symptom:** Report generation failure.
  - Inspect template path references in `reporting/report_generator.py`.
  - Validate data sources availability (Redis, analytics services).

## Social & Monitoring
- **Symptom:** Discord alerts missing.
  - Check webhook/credential validity.
  - Review rate limit warnings from API responses.
- **Symptom:** Dashboard stale data.
  - Confirm data fetchers running on schedule.
  - Validate API tokens for dashboard backend services.

## Escalation Path
1. Identify affected layer and notify owner listed in layer guide.
2. Gather logs, metrics snapshots, and recent changes.
3. If customer impact, open incident channel and document timeline.
4. After resolution, update this playbook and associated runbook.
