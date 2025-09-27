# Runbook: AlphaVantage Greeks Missing

## Scenario
The AlphaVantage real-time options response lacks Greeks data (`delta`, `gamma`, `theta`, `vega`, `rho`) even when `requiredGreeks=true` is supplied.

## Preconditions
- CARD_000 through CARD_002 completed
- Live API credentials verified in Phase 0 evidence folder

## Immediate Actions
1. Confirm the request includes `requiredGreeks=true` (inspect `logs/alphavantage_requests.log`).
2. Re-run the live check script:
   ```bash
   python scripts/live_checks/alpha_vantage_ping.py --symbol SPY --required-greeks true --verbose
   ```
3. If the payload still lacks Greeks, inspect the response metadata for entitlement flags; AlphaVantage may return `Information` messages indicating tier limitations.
4. Tag affected option quotes with `metadata.quality_flags += ['GREEKS_MISSING']` before publishing to downstream systems.
5. Notify analytics consumers via Slack/Teams channel with incident reference.

## Remediation
- Verify the premium tier entitlement covers the requested symbol/expiry (AlphaVantage dashboard > Account).
- Schedule a backfill job for the impacted timeframe once entitlements are restored (`scripts/stream_alpha.py --historical-date ...`).
- Update `docs/evidence/phase1/` with raw payload showing the issue and resolution timestamp.

## Postmortem Checklist
- Record incident in `docs/security/audit-log.md` and note corrective actions.
- Update `phase-1-data/layer-1-ingestion/README.md` revision history if process changed.
- Review rate limiter metrics to ensure requests are not being throttled (which can strip Greeks fields).
