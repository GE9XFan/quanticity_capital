# Runbook: Credential Rotation

## Purpose
Rotate AlphaVantage and IBKR credentials without disrupting ingestion services.

## Schedule
- AlphaVantage API key: quarterly (first business day).
- IBKR certificates/passwords: every 90 days or per broker policy.

## Preconditions
- Access to secrets manager (Vault path `kv/market-data/`).
- Config repository permissions.
- Change window approved.

## Rotation Steps
1. **Preparation**
   - Confirm maintenance window with stakeholders.
   - Retrieve current secret metadata for audit log.
2. **Generate New Credentials**
   - AlphaVantage: request new premium key via account portal.
   - IBKR: renew certificates and export password file according to broker instructions.
3. **Update Secrets Manager**
   - Store new values at `kv/market-data/alpha_vantage` and `kv/market-data/ibkr`.
   - Tag secrets with rotation date and operator (Michael Merrick).
4. **Validate Configurations**
   - Run `scripts/validate_contract.py alphavantage_rate_limit:v1.0.0 config/trading_params.yaml` to ensure config syntax intact.
   - Update `config/credentials.yaml` placeholders with secret references (no plaintext keys).
5. **Deploy to Staging**
   - Restart ingestion service with new secrets.
   - Execute smoke tests: `python scripts/stream_alpha.py --symbol SPY --duration 60` and `python scripts/stream_ibkr.py --symbol SPY --duration 60`.
6. **Promote to Production**
   - Roll restart ingestion pods/workers sequentially.
   - Monitor metrics for 30 minutes (`data_ingestion.alpha_vantage.latency_ms`, `data_ingestion.ibkr.disconnects`).
7. **Revoke Old Credentials**
   - Disable previous AlphaVantage key.
   - Remove old IBKR certificates/passwords.

## Post-Rotation Tasks
- Update rotation log in `appendices/troubleshooting.md` (credential section).
- File change ticket with evidence of tests and monitoring.
- Schedule next rotation reminder in calendar.

## Links
- Build Cards: `CARD_001`, `CARD_004`
- Tests: `tests/layer1/test_alphavantage_client.py`, `tests/layer1/test_ibkr_wrapper.py`
