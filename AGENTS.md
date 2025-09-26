# Quanticity Capital – Agents Guide

## Project Overview
- Automated options trading stack orchestrated by `src/quanticity_capital/main.py` with Redis as the data exchange hub and Postgres for persistence.
- Independent modules (scheduler, ingestion, analytics, signals, execution, watchdog, social, dashboard, observability) communicate only via Redis and shared database abstractions.
- Specs live under `docs/specs/`; consult them before touching the associated module. The `docs/implementation_plan.md` and `docs/master_plan.md` define sequencing and guardrails.

## Repository Layout & Intent
| Path | Purpose | Key Artifacts |
|------|---------|---------------|
| `config/` | YAML + env templates feeding the config loader. Separate files per subsystem (`runtime.yml`, `schedule.yml`, `symbols.yml`, `analytics.yml`, `watchdog.yml`, `observability.yml`). | `config/AGENTS.md`, `.env.example` | 
| `docs/` | Specifications, implementation plans, test records. | `docs/AGENTS.md`, `docs/specs/*.md` |
| `src/quanticity_capital/` | Python package hosting orchestrator, shared clients, and every runtime module. Subdirectories per subsystem (`scheduler/`, `ingestion/`, etc.) with their own `AGENTS.md`. | `main.py`, module packages |
| `tests/` | Unit and integration suites (`unit/`, `integration/`, `e2e/`). Integration tests hit live services, so gate them carefully. | `tests/AGENTS.md` |
| `tools/` | CLI utilities for diagnostics (`peek`, `scheduler`, `watchdog`). Scripts should be `uv run`-friendly. | `tools/AGENTS.md` |
| `dashboard/frontend/` | React + TypeScript UI scaffold (Vite). Keep backend in `src/quanticity_capital/dashboard/api/`. | `dashboard/frontend/AGENTS.md` |
| `alembic/` | Database migrations (`env.py`, `versions/`). | `alembic/AGENTS.md` |
| `logs/`, `backups/`, `data/` | Runtime output, PG dumps, captured datasets. Empty placeholders kept for path stability. | `.gitkeep` files |

Add module-specific AGENTS/README files inside new directories so agents can grab context without jumping back to root.

## Build & Tooling
- Dependency management: `uv sync` (Make target `make install`).
- Formatting & linting: `make fmt`, `make lint` (Ruff handles formatting + lint). Keep line length ≤ 100.
- Type checking: `make typecheck` (mypy).
- Tests: `make test` (pytest). Use `pytest -m "not integration"` when external services unavailable.
- Runtime entrypoint: `make run` → `uv run python3.11 src/main.py`.
- Node tooling (dashboard): `cd dashboard/frontend && npm install && npm run dev` once scaffolded.

## Runtime & Environment
- Required services: Redis (single node), Postgres (local), IBKR TWS/Gateway (paper), Alpha Vantage, OpenAI, Discord/Twitter/Telegram/Reddit APIs.
- Use `.env.example` as the base; load with `direnv` if available. Secrets must remain local.
- Scheduler cadences and symbol universes defined under `config/`—treat these as source-of-truth rather than hard-coding values.

## Code Style & Practices
- Prefer async-first patterns (`asyncio`, `TaskGroup`) per spec. Avoid cross-module imports that bypass Redis/DB hand-offs.
- Structured logging via `structlog` or configured `logging` dict. Emit heartbeats and metrics as described in specs.
- Package layout mirrors runtime boundaries; keep shared helpers in `src/quanticity_capital/core/`.
- Avoid mocks in integration tests—hit live services as mandated. Use fixtures to guard credentials and rate limits.

## Testing Guidance
- Unit tests focus on pure logic (parsers, sizing math). Keep them under `tests/unit/`.
- Integration tests (`tests/integration/`) require live Redis/Postgres and API keys. Gate execution with markers/env flags.
- End-to-end dry runs (`tests/e2e/`) should follow the phase plan: orchestrator + scheduler + ingestion baseline before expanding scope.
- Capture sample payloads or pg dumps in `docs/test-records/` or `data/snapshots/` and reference them in module AGENTS.

## Security & Compliance
- Never commit secrets; `.env.example` contains placeholders only.
- Rotate API keys regularly (document cadence in `config/observability.yml`).
- Watchdog autopilot stays disabled unless explicitly toggled. Record manual overrides in Postgres audit tables.
- Social connectors should default to sandbox/staging credentials when testing messaging.

## Contribution Workflow
- Branch naming: `feature/<module>-<short-desc>` or `fix/<module>-<issue-id>`.
- Commit messages: imperative ("Add scheduler state loader"), limit to concise scope. Reference specs when relevant.
- PR checklist: spec alignment confirmed, tests (unit + targeted integration) run, lint/typecheck clean, AGENTS updated if contract changed.
- Use GitHub drafts for WIP; request review once specs satisfied.

## Deployment & Operations
- Local orchestration: run Redis/Postgres via `brew services` or Docker, launch modules with `make run` (single orchestrator) or `honcho`/tmux when splitting processes for debugging.
- Future containerization: Dockerfiles per module grouped under `infrastructure/docker/` (placeholder). Target Google Cloud single VM with systemd services per spec when scaling beyond MacBook.
- Backups: nightly `pg_dump` into `backups/` with rotation; document script in `tools/`.

## Data & Integrations Notes
- Alpha Vantage scope reset outlined in `docs/specs/ingestion_alpha_vantage.md`; adhere to capability map before expanding symbols.
- IBKR ingestion must respect pacing; coordinate client IDs across ingestion/execution modules.
- Analytics outputs (`derived:*`) and Redis stream contracts live in corresponding module specs—do not diverge without updating documentation + consumers.

## Context Cascade
- Each major directory contains its own `AGENTS.md` (or README) summarizing local responsibilities and pointing back to relevant specs.
- When adding new submodules, drop an `AGENTS.md` alongside the package to describe inputs/outputs and how it links to the rest of the stack.
- If multiple AGENTS apply, closest-in-path document overrides higher-level guidance but should cite the upstream context.

Stay aligned with the sequencing in `docs/implementation_plan.md`; phase gates exist to protect against scope creep and rate-limit surprises.
