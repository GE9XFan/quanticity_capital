# Alembic Configuration

This directory will hold Alembic config (`env.py`, `script.py.mako`) and migration versions under `versions/`.

## Next Steps
- Run `uv run alembic init alembic` once models solidify, or copy existing templates.
- Configure target metadata from `src/quanticity_capital/datastore/models.py`.
- Keep migrations in sync with specs in `docs/specs/trade_store.md` and module changes.
