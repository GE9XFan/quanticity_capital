# Observability & Alerting Module

## Purpose
Provide cross-cutting visibility into system health, latency, error conditions, and data freshness with minimal overhead.

## Responsibilities
- Collect metrics from modules and publish to Redis hashes (`metrics:*`).
- Monitor heartbeat keys for expiry and raise alerts via Telegram/email webhook.
- Manage log rotation and centralize log configuration.
- Provide CLI/reporting tooling for diagnostics.

## Components
1. **Heartbeat Monitor**
   - Scheduler job every 15s.
   - Scans `system:heartbeat:*`; if stale (>2× expected interval), emits alert event and logs.
2. **Data Freshness Monitor**
   - Background loop every 30s.
   - Uses ingestion metadata keys (`state:ingestion:...`) to validate that each feed has been refreshed within an acceptable age window rather than relying purely on Redis TTLs.
   - Publishes summary to `state:health:data` and alerts to `state:health:alerts` when stale feeds detected.
3. **Metrics Aggregator**
   - Periodically (60s) snapshot metrics into Postgres `audit.integration_runs` for historical analysis.
4. **Alert Dispatcher**
   - Integrates with Telegram bot or email (SMTP) to notify on severe events (module crash, rate-limit exhaustion, missing data).
5. **Log Management**
   - Configure Python logging via dictConfig; per-module logs under `logs/` with rotation (50 MB × 5).
   - Provide script to tail logs (`tools/tail_logs.py`).

## Alerts Severity
- **Critical:** orchestrator crash, Redis/Postgres unavailable, IBKR disconnect > 60s.
- **High:** Alpha Vantage failure streak > 5, scheduler tokens depleted for > 1 min, stale analytics > 3 cycles.
- **Medium:** Social queue backlog > threshold, pending approvals older than 15m.

## Configuration
- `config/observability.yml`: thresholds, contact points, alert cooldowns.
- Environment: `TELEGRAM_ALERT_BOT_TOKEN`, `TELEGRAM_ALERT_CHAT_ID`, optional email settings.

## Integration Testing
- Simulate heartbeat failure by stopping module; verify alert delivered.
- Trigger metric threshold exceedance (e.g., artificially set backlog) and confirm escalation.
- Validate log rotation by generating sample logs beyond size threshold.
