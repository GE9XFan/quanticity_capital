# Quantum Trading System Implementation Guides

Purpose of this tree: keep implementation state, contracts, and runbooks aligned with the architecture described in `quantum-trading-architecture.md`. Every layer should have a living guide that tracks status, owners, outstanding blockers, and verification evidence.

## How to Use This Knowledge Base
- Start with `timeline.yaml` for the phase sequence and target dates.
- Review `phase-metrics.yaml` and `VALIDATION_CHECKLIST.md` before promoting any layer to the next phase.
- Capture interface guarantees in `contracts/` first, then draft the layer guide using `LAYER_TEMPLATE.md`.
- Break delivery work into Build Cards (`build-cards/`) so each task has objective success criteria and test hooks.
- Keep `dependencies.lock` updated whenever a contract changes or a new downstream consumer emerges.

## Directory Map
```
README.md                  # You are here
phase-metrics.yaml         # Key success criteria per phase
timeline.yaml              # Milestones, owners, and confidence bands
VALIDATION_CHECKLIST.md    # Promotion checklist for phase exits
LAYER_TEMPLATE.md          # Living doc template for any layer
../agents.md               # Agent & automation governance playbook (must read first)

phase-0-foundations/       # Environment & prerequisite checklist before Phase 1
phase-1-data/              # Detailed guides for data acquisition & storage
build-cards/               # Task-level build instructions
contracts/                 # Canonical interface definitions
appendices/                # Shared references (config, monitoring, troubleshooting)
```

## Operating Principles
- **Contracts First:** define payloads and API expectations before coding.
- **Evidence Driven:** do not mark checklist items complete without linkable proof (tests, observability dashboards, runbooks).
- **Immutable History:** version every contract in `contracts/` and record changes in `contracts/version-history.md`.
- **Cross-Layer Visibility:** use `dependencies.lock` to understand upstream/downstream impact before deploying changes.
- **Repeatable Validation:** each Build Card must specify verification steps so QA can replay success criteria.

## Next Actions
1. Read `agents.md` to understand roles, escalation paths, and evidence requirements.
2. Confirm `phase-0-foundations/README.md` is executed and evidenced before touching ingestion code.
3. Populate the layer-specific READMEs under `phase-1-data/` using the template.
4. Register build cards and keep them aligned with the architecture requirements (no ad-hoc scope drift).
5. Fill in contract schemas in `contracts/v1.0.0/` and log lineage in the version history.
