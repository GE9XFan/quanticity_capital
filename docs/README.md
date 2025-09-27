# Documentation Index

## Purpose
Provide a single entry point for all planning, setup, and module specifications so a solo developer
can navigate the project without chasing files across the repo.

## How to Use This Index
- Start with `docs/setup.md` for environment bootstrap, installation commands, and repository layout.
- Review implementation roadmaps (`docs/implementation_plan.md`, `docs/master_plan.md`) for phase
  context.
- Consult domain references (`docs/data_sources.md`) and module guides (`docs/modules.md`) while
  developing specific features.
- Update this table whenever new documents are added or existing ones move.

## Current Documents
| Area | Document | Notes |
|------|----------|-------|
| Setup & Tooling | `docs/setup.md` | Bootstrap instructions plus verification commands for the repository skeleton. |
| Planning | `docs/implementation_plan.md` | Near-term build order; Phases 0–2 are complete, Phase 3 (IBKR connectivity) is next. |
| Planning | `docs/master_plan.md` | Long-term vision with explicit callouts for future phases. |
| Data References | `docs/data_sources.md` | Live Alpha Vantage contracts from Phase 2 plus placeholders for upcoming modules. |
| Modules | `docs/modules.md` | Outline of planned modules; implementation pending future phases. |
| Operations | `docs/cli_operations.md` | Tracks CLI entry points; Phase 2 covers the live Alpha Vantage runner and scheduler. |
| Samples | `docs/samples/alpha_vantage/` | Source JSON captured from live endpoints, used for documentation and ingestion tests. |

## Maintenance Rules
- Keep file names flat within `docs/` unless a new category absolutely requires nesting.
- When a stub grows beyond a few screens, consider splitting it, but always link the new file here.
- Re-run links after renaming files to avoid stale references.
- Update this index whenever pointers change so newcomers know exactly what lives in the repository
  today.
