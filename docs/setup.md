# Local Environment & Tooling Guide

## Target Platform
- macOS Sonoma (13/14+) on Apple Silicon or Intel.
- Python 3.11.x from python.org or Homebrew.
- Redis (local service) reachable via `redis://127.0.0.1:6379/0`.
- PostgreSQL 16 installed locally with superuser access.

## First-Time Bootstrap
1. **Install Python 3.11**
   ```bash
   brew install python@3.11
   ```
   or download the official installer from python.org and ensure `python3.11` is on PATH.

2. **Create virtual environment at repo root**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip setuptools wheel
   ```

3. **Copy environment template**
   ```bash
   cp .env.example .env
   ```
   Fill in API keys and connection strings as they become available.

4. **Install base dependencies**
   ```bash
   python -m pip install -r requirements.txt
   ```

## Daily Workflow
```bash
cd /Users/michaelmerrick/quanticity_capital
source .venv/bin/activate
python -m pip install --upgrade pip  # optional weekly
python -m pip install -r requirements.txt
```

## Python Dependencies
- Maintain a single `requirements.txt` with pinned versions (e.g., `httpx==0.27.0`).
- When adding a library: install into the venv, run `pip freeze | grep <package>` to capture the exact version, update `requirements.txt`, and annotate purpose in-line using comments sparingly.
- Reinstalling requirements should never downgrade unintentionally; review `pip` output for warnings.

## Tooling Norms
- **Formatting/Linting:** Default to `ruff` if/when added; do not introduce `black` or `pre-commit` without prior agreement.
- **Testing:** Use `pytest` for unit/integration tests. Invoke with `pytest -q` from repo root.
- **Logging:** All scripts should rely on structured logging helpers once defined under `src/core/logging.py` (placeholder).
- **CLI helpers:** document recurring commands in `docs/reference/cli_workflow.md` (to be created).

## Redis & Postgres Expectations
- Redis runs locally with persistence disabled (default configuration). Keys should include TTL metadata; see `docs/data_sources.md` for naming conventions.
- PostgreSQL 16 local database `quanticity_capital` with user/password stored in `.env`. Future migrations handled via Alembic.

## Verification Checklist
- `python --version` → `Python 3.11.x` inside venv.
- `redis-cli PING` → `PONG`.
- `psql -d quanticity_capital -c '\dt'` → succeeds (empty list acceptable initially).
- `pytest` passes (when tests exist).

## Ongoing Maintenance
- Keep `.env.example` updated when new environment variables are required.
- Run `pip list --outdated` monthly to plan dependency upgrades; bump deliberately with changelog review.
- Capture troubleshooting notes (install errors, version conflicts) in `docs/setup.md` under new headings as they arise rather than scattering across other docs.
