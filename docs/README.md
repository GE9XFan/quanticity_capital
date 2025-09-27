# Documentation Index

## Purpose
Provide a single entry point for all planning, setup, and module specifications so a solo developer can navigate the project without chasing files across the repo.

## How to Use This Index
- Start with `docs/setup.md` for environment bootstrap and recurring tooling commands.
- Move to implementation roadmaps (`docs/implementation_plan.md`, `docs/master_plan.md`) for phase context.
- Consult domain references (`docs/data_sources.md`) and module guides (`docs/modules.md`) while developing specific features.
- Update this table whenever new documents are added or existing ones move.

## Current Documents
| Area | Document | Notes |
|------|----------|-------|
| Setup & Tooling | `docs/setup.md` | Environment bootstrap, dependency policy, CLI workflow. |
| Planning | `docs/implementation_plan.md` | Reset-specific task sequencing. |
| Planning | `docs/master_plan.md` | System vision and phase roadmap. |
| Data Sources | `docs/data_sources.md` | Alpha Vantage, IBKR, and future feeds (stub). |
| Modules | `docs/modules.md` | Analytics, signals, execution, scheduler, observability (stub). |
| Specs Archive | `docs/specs/` | Prior spec drafts; keep for reference until merged into new guides. |
| Operations | `docs/cli_operations.md` | CLI command glossary and incident playbooks. |

## Maintenance Rules
- Keep file names flat within `docs/` unless a new category absolutely requires nesting.
- When a stub grows beyond a few screens, consider splitting it, but always link the new file here.
- Re-run links after renaming files to avoid stale references.
