# Tools Directory Guide

Hold developer utilities that are executed with `uv run python tools/<script>.py`.

Suggested scripts:
- `peek.py` – inspect Redis keys (`python tools/peek.py raw:options:SPY`).
- `scheduler_dump.py` – print scheduler state hashes for debugging.
- `watchdog_replay.py` – replay stored analytics/signals through watchdog for evaluation.
- `pg_backup.py` – wrapper around `pg_dump` to populate `backups/`.

Ensure scripts are CLI-friendly and documented in root `AGENTS.md` when new utilities are added.
