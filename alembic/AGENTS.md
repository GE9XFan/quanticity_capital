# Alembic Configuration

This directory contains the Alembic config (`alembic.ini`, `env.py`, `script.py.mako`) and migration versions under `versions/`.

## Usage
- Baseline revision `20240925_0001` creates schemas `reference`, `trading`, `analytics`, `audit` and their core tables per `docs/specs/trade_store.md`.
- `env.py` loads metadata from `src/quanticity_capital/datastore/models.py`; keep models and migrations aligned.
- Generate new revisions with `uv run alembic revision --autogenerate -m "<summary>"` and review SQL before upgrading.
- Apply migrations locally with `uv run alembic upgrade head`.
