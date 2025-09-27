# CLI & Operations Reference

A lightweight CLI ships with the repository skeleton. Use this page to track entry points,
document flags, and capture operational runbooks as additional commands land.

## Current Status
- `quanticity-capital` (or `python -m quanticity_capital.main`) bootstraps logging, supports
  `--log-level`/`--version`, and exposes the production `ingest alpha-vantage` sub-command delivered
  in Phase 2.
- Alpha Vantage orchestration persists payloads to Redis with metadata envelopes and TTL guardrails
  defined under `services.redis` in `config/settings.yaml`; integration tests validate runner,
  scheduler, and orchestrator wiring.
- A trading-hours scheduler (`--schedule`) is available and mirrored in the project `Procfile` for
  process-manager integration.
- The Makefile still focuses on dependency helpers; no automated deploy targets exist yet.

## Quick Usage
```bash
# Inside an activated virtual environment
quanticity-capital --help
quanticity-capital --log-level DEBUG
python -m quanticity_capital.main --version
python -m quanticity_capital.main ingest alpha-vantage --help
```

## Alpha Vantage Ingestion

### Manual runs
```bash
# Execute all configured endpoints once
python -m quanticity_capital.main ingest alpha-vantage

# Limit to a single endpoint context
python -m quanticity_capital.main ingest alpha-vantage \
  --endpoint NEWS_SENTIMENT --interval 0 --max-iterations 1

# Preview the job plan without calling the API
python -m quanticity_capital.main ingest alpha-vantage --dry-run
```
- `--interval <seconds>` combined with `--max-iterations` retains the simple looping behaviour for
  backfills and diagnostics.
- `--api-key` overrides the environment variable defined by `services.alphavantage.api_key_env`.

### Scheduled trading-hours mode
```bash
# Poll every 2 minutes, refreshing jobs once TTL <= 2 minutes
python -m quanticity_capital.main ingest alpha-vantage \
  --schedule --interval 120 --refresh-guard-seconds 120
```
- Scheduler only dispatches jobs during US trading hours (09:30–16:00 `America/New_York`).
- Jobs are skipped until their Redis TTL drops below `--refresh-guard-seconds`, preventing redundant
  vendor calls.
- `--schedule` cannot be combined with `--dry-run` and requires Redis persistence to be enabled
  (default behaviour).

### Procfile integration
```
alpha_vantage_scheduler: python -m quanticity_capital.main ingest alpha-vantage --schedule
```
Run with `foreman start`, `honcho start`, or `heroku local` to supervise the scheduler alongside other
services.

## Next Steps (Phase 3 and beyond)
- Add IBKR connectivity commands (quotes, positions, executions) once Phase 3 lands, including
  environment variables, guardrails, and rollback steps.
- Capture incident response flows for ingestion, analytics, signal, and execution modules as they
  graduate from the backlog.
- Provide copy-pasteable commands only after verifying them against the live codebase.

Keep this file aligned with the live repository so operational context stays trustworthy.
