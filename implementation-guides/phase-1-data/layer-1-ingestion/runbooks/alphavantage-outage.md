# Runbook: AlphaVantage Outage

## Purpose
Restore AlphaVantage data ingestion when external API outages or rate limit breaches occur.

## Detection
- Alert `data_ingestion.alpha_vantage.error_rate > 5%` for 5 minutes.
- Alert `data_ingestion.rate_limit.tokens_available < 10` for 30 seconds.
- Operator notification from vendor status page or Slack channel `#market-data`.

## Preconditions
- Access to Redis and ingestion service logs.
- AlphaVantage credentials in vault.
- Monitoring dashboard link: `analytics.grafana/alpha_vantage_overview`.

## Response Steps
1. **Acknowledge Alert**
   - Record incident start time in incident tracker.
2. **Validate Rate Limiter State**
   - Run `redis-cli GET rate_limit:alpha_vantage:current_tokens`.
   - If tokens negative, execute `scripts/simulate_av_load.py --dry-run` to reproduce and gather metrics.
3. **Check Vendor Status**
   - Visit <https://www.alphavantage.co/support/#support> for outage reports.
   - If confirmed outage, proceed to fallback.
4. **Enable Cached Fallback**
   - Toggle `config/trading_params.yaml::alpha_vantage.use_cache_only = true`.
   - Redeploy ingestion service with annotation `DEGRADED_SOURCE`.
5. **Throttle Polling Cadence**
   - Reduce `requests_per_minute` by 20% via configuration update.
   - Validate config using `scripts/validate_contract.py alphavantage_rate_limit:v1.0.0 config/trading_params.yaml`.
6. **Communicate Status**
   - Trigger observability notification workflows delivered in `CARD_006`.
   - Notify stakeholders in `#ops` channel.
7. **Monitor Recovery**
   - Observe latency and error metrics for 30 minutes.
   - Re-enable real-time mode once API stabilizes (<1% errors for 15 minutes).

## Post-Recovery Actions
- Restore original rate limit configuration and redeploy.
- Update incident log with root cause and corrective actions.
- Schedule retrospective if outage >1 hour.

## Links
- Build Cards: `CARD_001`, `CARD_002`
- Contracts: `alphavantage_rate_limit:v1.0.0`, `option_chain:v1.0.0`
- Tests: `tests/layer1/test_rate_limiter.py`, `tests/layer1/test_option_normalizer.py`
