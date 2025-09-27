# BUILD CARD 000: Phase 0 Environment Baseline

**Difficulty:** ⭐⭐☆☆☆
**Time:** 6 hours
**Prerequisites:**
- Access to AlphaVantage premium keys and IBKR paper credentials
- Docker Desktop (or Colima) installed with Compose v2 support
- Secrets manager entry created for trading system credentials

## Objective
Stand up the full development environment (Python toolchain, Redis Stack, telemetry, live check scripts) and capture evidence that both AlphaVantage and IBKR integrations respond successfully in the target network.

## Success Criteria
- [ ] `python scripts/live_checks/alpha_vantage_ping.py --symbol SPY --required-greeks true` returns a populated options chain with Greeks metadata
- [ ] `python scripts/live_checks/ibkr_gateway_ping.py --host 127.0.0.1 --port 4002` confirms gateway heartbeat and available market data subscriptions
- [ ] Redis Stack, Prometheus, and Grafana containers running via `docker compose ps --status running`
- [ ] Agents roster (`agents.md`) acknowledged and escalation contacts recorded
- [ ] Credentials stored in `config/credentials.yaml` with checksum recorded in secrets manager

## Implementation
1. Read `agents.md`, capture acknowledgement in `docs/evidence/phase0/agents_ack.md`, and ensure contacts/escalations are documented.
2. Follow `phase-0-foundations/README.md` to clone upstream repositories and install dependencies without modifying vendor code.
3. Create the `scripts/live_checks/` directory with AlphaVantage and IBKR ping scripts (reuse samples from vendor repos, only wrap logging/CLI handling).
4. Update `.env.example` and `config/credentials.yaml.example` with any new variables introduced by the live check scripts.
5. Launch infrastructure with `docker compose --profile redis --profile monitoring up -d` and verify container health.
6. Run both live check scripts, store stdout in `docs/evidence/phase0/` (create directory) with timestamped filenames.
7. Upload Grafana dashboard snapshot (`dashboards/environment_foundations.json`) after verifying AlphaVantage/IBKR latency panels populate.

## Verification
- Attach the command outputs and dashboard snapshot to `docs/evidence/phase0/` and link them in `VALIDATION_CHECKLIST.md`.
- Note the completion date in `timeline.yaml` Phase 0 milestone.
- Confirm build card closure by ticking Phase 0 section in `phase-0-foundations/README.md`.

## Links to Next Cards
- [CARD_001](CARD_001.md): AlphaVantage Client Integration
- [CARD_004](CARD_004.md): IBKR Tick Stream Harmonization (after Phase 0 IBKR readiness confirmed)
