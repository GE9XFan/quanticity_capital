# Source Tree Overview

`src/` houses the Python runtime packaged as `quanticity_capital`. Follow the module boundaries defined in `docs/specs/`—each subpackage mirrors a spec. Prefer dependency injection via Redis/Postgres clients rather than tight coupling.

Key entry points:
- `quanticity_capital/main.py` – orchestrator bootstrap.
- `quanticity_capital/config/` – configuration loader + models wrapping the YAML in `config/`.
- `quanticity_capital/core/` – shared clients/utilities (Redis, Postgres, logging).
- `quanticity_capital/scheduler/` – token buckets, job registry, persistence.
- `quanticity_capital/ingestion/` – Alpha Vantage + IBKR workers (async).
- `quanticity_capital/analytics/` – analytics engine and metric plugins.
- `quanticity_capital/signals/` – strategy evaluators and sizing logic.
- `quanticity_capital/execution/` – IBKR order routing, risk guardrails.
- `quanticity_capital/watchdog/` – OpenAI review workflow.
- `quanticity_capital/social/` – queue + connectors for outbound messaging.
- `quanticity_capital/dashboard/` – FastAPI backend scaffolding.
- `quanticity_capital/observability/` – heartbeat monitor, metrics, alert dispatcher.
- `quanticity_capital/datastore/` – Postgres migrations + DAL.
- `quanticity_capital/cli/` – developer-facing CLI commands (scheduler inspector, payload peek).

Each subdirectory contains its own `AGENTS.md` to document contracts, Redis keys, and integration points.
