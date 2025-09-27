# Error Recovery & Resilience

## Purpose
Document recovery procedures for AlphaVantage and IBKR ingestion failures to maintain continuous data availability.

## Failure Scenarios
| Scenario | Detection | Response |
|----------|-----------|----------|
| AlphaVantage 5xx errors | Spike in `data_ingestion.alpha_vantage.error_rate` | Retry with exponential backoff, fail over to cached data, notify ops |
| AlphaVantage 429 | Rate limiter exhaust alert | Throttle polling cadence, investigate bursty workloads |
| IBKR disconnection | `data_ingestion.ibkr.disconnects` metric, missing heartbeat | Invoke reconnect runbook, pause new subscriptions, alert ops |
| IBKR pacing violation | Error code 10147 in logs | Back off subscription cadence, adjust client IDs, notify execution team |
| Normalizer exception | Schema validation failures | Quarantine payload, log sample for analysis, continue processing |

## Recovery Playbooks
1. **AlphaVantage Outage**
   - Switch ingestion to cached data stream and mark quality flag `DEGRADED_SOURCE`.
   - Notify analytics consumers via `status` event.
   - Monitor vendor status page and schedule retry every 5 minutes.
2. **IBKR Gateway Restart**
   - Stop ingestion workers gracefully.
   - Restart TWS/Gateway, verify connectivity.
   - Rehydrate subscriptions from configuration snapshot.
   - Reconcile missed ticks using `reqHistoricalData` once live.
3. **Schema Drift**
   - Fail validation fast and create incident ticket.
   - Roll back to last known good release or hotfix mapping layer.
   - Update contract and downstream consumers before re-enable.

## Runbook References
- `runbooks/alphavantage-outage.md` (TBD)
- `runbooks/ibkr-reconnect.md` (TBD)
- `runbooks/schema-drift.md` (TBD)

## Post-Mortem Requirements
- Capture timeline, root cause, and follow-up tasks in incident template.
- Update layer guide risk section with new mitigations.
- Align changes with `dependencies.lock` if contracts updated.
