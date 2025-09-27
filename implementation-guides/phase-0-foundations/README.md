# Phase 0: Environment & Dependency Foundations

## Status Dashboard
```yaml
status: NOT_STARTED
completion: 0
blockers: []
last_updated: 2025-09-27
owner: Michael Merrick
```

## Mission & Scope
- Establish the local and cloud environments required by Phase 1 before any ingestion code changes begin.
- Wire up the vetted upstream repositories documented in `quantum-trading-architecture.md` so we reuse proven clients instead of rebuilding them.
- Validate credential management, network access, and observability plumbing with real AlphaVantage and IBKR API calls.

## Deliverables
1. Local dev stack with Python 3.11, Redis Stack, and telemetry agent installed.
2. Secrets vaulted and surfaced through `config/credentials.yaml` / env vars with CI-safe templating.
3. Verified connectivity to AlphaVantage (premium) and IBKR paper trading endpoints using the reference scripts.
4. Baseline observability: Prometheus agent scraping local exporters, Grafana dashboard placeholder imported.
5. Documentation updates: `.env.example`, `config/` templates, runbook anchors.

## Execution Checklist
- [ ] Read `agents.md` and record acknowledgement in onboarding notes.
- [ ] Clone/extract the sanctioned integration repositories:
  - `https://github.com/RomelTorres/alpha_vantage` (Python package already on PyPI).
  - `https://github.com/erdewit/ib_insync` (wrapper patterns referenced by `ib_async`).
  - `https://github.com/IBKR/api-samples` (official tick/feed examples).
- [ ] Install base dependencies: `pip install -r requirements.txt` plus `poetry install` if using the Poetry workflow.
- [ ] Bootstrap infrastructure:
  - Start Redis Stack via `docker compose --profile redis up -d`.
  - Launch Prometheus/Grafana docker compose profile for local metrics.
- [ ] Configure secrets: populate `config/credentials.yaml` from `credentials.yaml.example` and export `ALPHAVANTAGE_API_KEY`, `IBKR_USER`, `IBKR_PASSWORD`, `IBKR_ACCOUNT`.
- [ ] Verify network paths:
  - AlphaVantage sanity test: create (or update) `scripts/live_checks/alpha_vantage_ping.py` and run `python scripts/live_checks/alpha_vantage_ping.py --symbol SPY --required-greeks true`.
  - IBKR gateway heartbeat: create (or update) `scripts/live_checks/ibkr_gateway_ping.py` and run `python scripts/live_checks/ibkr_gateway_ping.py --host 127.0.0.1 --port 4002`.
- [ ] Validate telemetry: ensure metrics from Redis, AlphaVantage scripts, and IBKR ping appear in Grafana `Environment Foundations` dashboard (imported from `dashboards/environment_foundations.json`).
- [ ] Sign off readiness in `VALIDATION_CHECKLIST.md` (new Phase 0 section).

## Evidence to Capture
- Signed acknowledgement file `docs/evidence/phase0/agents_ack.md` with names, roles, timestamp.
- Screenshot or export of Grafana dashboard showing live API latency panels.
- CLI output from both live check scripts with timestamps.
- Hash of `config/credentials.yaml` stored in 1Password/Secrets Manager entry.

## Risks & Mitigations
- **Missing vendor entitlements:** confirm AlphaVantage premium and IBKR market data allocations before Phase 1 kickoff. Document entitlement IDs in `credentials.yaml` notes.
- **Local firewall restrictions:** record required outbound ports (AlphaVantage HTTPS, IBKR 4001/4002) in onboarding runbook and confirm with IT.
- **Secret leakage:** use `.envrc` or direnv to scope environment variables and add audit entry in `docs/security/audit-log.md`.

## Exit Criteria
Phase 0 completes when:
- Agents playbook acknowledgement is stored in `docs/evidence/phase0/agents_ack.md`.
- Both live API checks succeed within the same working session (no retries required).
- Redis + telemetry stack run for 4 consecutive hours without error in logs.
- `VALIDATION_CHECKLIST.md` Phase 0 items all marked complete with evidence links.
- Phase 1 Build Cards updated to reference the environment artifacts (scripts, configs).
