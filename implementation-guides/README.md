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
1. Populate the layer-specific READMEs under `phase-1-data/` using the template.
2. Register initial Build Cards for the immediate ingestion and storage backlog.
3. Fill in contract schemas in `contracts/v1.0.0/` and log lineage in the version history.
