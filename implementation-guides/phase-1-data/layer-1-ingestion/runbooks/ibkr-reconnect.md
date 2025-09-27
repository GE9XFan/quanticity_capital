# Runbook: IBKR Session Reconnect

## Purpose
Recover Interactive Brokers data ingestion after disconnects, pacing violations, or gateway restarts.

## Detection
- Alert `data_ingestion.ibkr.disconnects > 0` within 5 minutes.
- Missing heartbeats from `ib_async` supervisor for >15 seconds.
- Pacing violation error `10147` in logs.

## Preconditions
- SSH access to ingestion host.
- Credentials to IBKR TWS/Gateway.
- Monitoring dashboard: `analytics.grafana/ibkr_connectivity`.

## Response Steps
1. **Pause New Orders/Subscriptions**
   - Set feature flag `config/trading_params.yaml::ibkr.ingestion_enabled = false`.
   - Notify execution desk about data degradation.
2. **Inspect Logs**
   - Tail ingestion logs: `tail -f logs/ibkr/ingestion.log`.
   - Capture last 200 lines for incident notes.
3. **Verify Gateway Status**
   - Check TWS/Gateway UI or API to confirm connection state.
   - Restart service if unresponsive.
4. **Reset Client IDs**
   - Run `redis-cli DEL ibkr:next_client_id` if necessary (after confirming no active sessions).
   - Update `config/trading_params.yaml::ibkr.client_ids` if collision detected.
5. **Reconnect**
   - Execute management command: `python scripts/ibkr_manage.py reconnect --env prod` (stub).
   - Confirm `IB.connectAsync` success and heartbeats resumed.
6. **Resubscribe Streams**
   - Trigger `scripts/stream_ibkr.py --symbol SPY --duration 120` to verify feed health.
   - Monitor metrics `data_ingestion.ibkr.latency_ms` and `data_ingestion.ibkr.reconnects`.
7. **Re-enable Ingestion**
   - Set `ibkr.ingestion_enabled = true`.
   - Announce recovery in `#ops` channel.

## Post-Recovery Actions
- File incident summary with root cause.
- Review pacing guard configuration (`CARD_004`).
- Schedule reconnection drill if not performed in last 90 days.

## Links
- Build Cards: `CARD_004` (IBKR Normalization), `CARD_006` (Ingestion Monitoring)
- Contracts: `option_chain:v1.0.0`, `market_data:v1.0.0`
- Tests: `tests/layer1/test_ibkr_wrapper.py`
