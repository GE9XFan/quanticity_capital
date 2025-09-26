# CLI Utilities

Expose developer tooling under `python -m quanticity_capital.cli`. Commands should help inspect Redis payloads, scheduler state, ingestion health, and manual overrides.

## Suggested Commands
- `peek` – pretty-print Redis key contents (`tools/peek.py` equivalent).
- `scheduler` – view job queues, token levels, force enqueue jobs.
- `ingestion` – check last run times per symbol/feed.
- `orders` – manual cancel/amend hooks for execution engine.

Use `typer` or `click` for UX; keep commands composable and aware of async environment.
