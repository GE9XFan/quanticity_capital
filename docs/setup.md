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

## Bootstrap Command Reference (September 2025 Reset)
```bash
# From repo root
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
cp .env.example .env  # now populated locally (ALPHAVANTAGE_API_KEY=demo, etc.)
python -m pip install -r requirements.txt
python --version      # expect Python 3.11.x inside venv
which python          # should resolve to .venv/bin/python
```

### Repository Layout (Phase 1)
- `src/core/`: configuration, logging, Redis helpers.
- `src/ingestion/`: schedulers and vendor ingestion modules (skeleton today).
- `src/analytics/`: analytics configuration loader and future workers.
- `config/`: runtime manifests (`runtime.yml`, `analytics.yml`, vendor configs as they arrive).
- `tests/`: pytest suite covering configuration + scheduler scaffolding.
- `docs/`: runbooks, setup notes, verification artefacts.

Redis task queues currently live under `queue:analytics` (list). Enqueued payload schema:
```json
{
  "job": {"name": "refresh_high_frequency", "type": "analytics.refresh.high_frequency", ...},
  "queued_at": "2025-09-26T12:00:00Z",
  "retry_count": 0
}
```
Workers must pop from the queue, process analytics, and record status/metrics per the governance
guide.

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

### Environment Variables
- `APP_ENV`: environment prefix (`dev`/`staging`/`prod`). Scheduler/workers will prepend this to
  Redis keys once multi-env support is enabled.
- `ANALYTICS_CONFIG_PATH`: override for `config/analytics.yml` when testing alternative manifests.
- Maintain `.env.example` in lockstep with any new variables and document defaults/rationales here.

## Verification Checklist
- `python --version` → `Python 3.11.x` inside venv.
- `redis-cli PING` → `PONG`.
- `psql -d quanticity_capital -c '\dt'` → succeeds (empty list acceptable initially).
- `pytest` passes (when tests exist).

## Ongoing Maintenance
- Keep `.env.example` updated when new environment variables are required.
- Run `pip list --outdated` monthly to plan dependency upgrades; bump deliberately with changelog review.
- Capture troubleshooting notes (install errors, version conflicts) in `docs/setup.md` under new headings as they arise rather than scattering across other docs.
