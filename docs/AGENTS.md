# Documentation Guide

## Contents
- `master_plan.md` – system vision, guiding principles, module map, redis namespace.
- `implementation_plan.md` – phased roadmap (42-day baseline) with sequencing for module delivery.
- `specs/` – module-level specs; each filename matches the subsystem in `src/quanticity_capital/`.
- `test-records/` – captured payloads, integration artifacts, benchmarking notes (populate as modules come online).

## Usage
- Treat specs as living contracts. Update them when behavior changes and annotate AGENTS/README files accordingly.
- Keep architecture diagrams and TTL tables current—dashboard, ingestion, and analytics rely on shared expectations.
- When writing code, cite the relevant spec section in PR descriptions to maintain traceability.

## Adding New Docs
- For new modules, add a spec under `docs/specs/` and cross-link it from the closest AGENTS file.
- Store runbooks and operational checklists alongside module specs (e.g., `docs/specs/orchestrator_runbook.md`).
