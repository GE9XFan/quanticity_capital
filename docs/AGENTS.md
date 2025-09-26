# Documentation Guide

## Core References
- `master_plan.md` – long-term architecture and vision (kept for context; defer execution until the simplified pipeline is stable).
- `implementation_plan.md` – current roadmap centered on Python 3.11 + venv setup followed by sequential delivery: Environment → Alpha Vantage → IBKR → Analytics.
- `setup.md` – step-by-step local environment checklist (venv activation, requirements install, `.env` preparation).
- `alpha_vantage_endpoints.md` – live tracker for handshake status, TTLs, and verification artifacts per Alpha Vantage endpoint.
- `specs/` – module-level contracts; update the relevant spec (e.g., `specs/ingestion_alpha_vantage.md`) whenever implementation details change.

## Usage Expectations
- Record every Alpha Vantage iteration in `alpha_vantage_endpoints.md` before writing code; capture verification outputs under `docs/verification/` and note them in the tracker.
- Keep `implementation_plan.md` and the associated specs synchronized—any change to sequencing or prerequisites must be reflected in both locations.
- Update this AGENTS file whenever new documentation touchpoints are introduced so maintainers know where to look first.

## Adding New Docs
- Place new runbooks or checklists alongside the modules they support (e.g., ingestion verification steps under `docs/verification/`).
- Cross-link new specs from the appropriate AGENTS files in `src/` to keep navigation consistent.
- Note platform-specific guidance (macOS, Windows) inside `setup.md` or module runbooks rather than duplicating instructions here.
