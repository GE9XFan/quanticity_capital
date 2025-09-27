# Local Environment & Tooling Guide

The repository now ships a minimal Python package, configuration templates, and a smoke test suite to
prove the build pipeline. Follow the steps below to spin up a virtual environment, install the
package in editable mode, and run the verification commands.

## Target Platform
- macOS Sonoma (13/14+) on Apple Silicon or Intel.
- Python 3.11.x from python.org or Homebrew.
- Redis (local or remote) is required for the live Alpha Vantage ingestion runner; PostgreSQL remains
  optional until analytics and execution modules land.

## First-Time Bootstrap
1. **Install Python 3.11**
   ```bash
   brew install python@3.11
   ```
   or download the installer from python.org and ensure `python3.11` is on PATH.

2. **Create and activate a virtual environment at the repo root**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip setuptools wheel
   ```

3. **Install the package (editable) plus dev extras**
   ```bash
   python -m pip install -e .[dev]
   ```
   This pulls the dependencies declared in `pyproject.toml` and the pytest extra. A pinned
   `requirements.txt` remains for compatibility with older tooling; keep it in sync whenever
   dependencies change.

4. **Copy environment templates (optional today)**
   ```bash
   cp .env.example .env
   cp config/settings.example.yaml config/settings.yaml
   ```
   Populate the copied files with real credentials when upstream services are available.

### Quick Reference
```bash
# From repo root
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .[dev]
 pytest
```

## Verification Commands
- `pytest` — runs the repository smoke suite (currently validates package import + CLI execution).
- `python -m quanticity_capital.main --help` — prints CLI usage for manual checks.
- `quanticity-capital --version` — exercises the console script entry point.
- `python -m quanticity_capital.main ingest alpha-vantage --dry-run` — confirms job planning without
  vendor calls once `ALPHAVANTAGE_API_KEY` and `REDIS_URL` are configured.

## Current Repository Layout
- `src/quanticity_capital/` — Python package stub with logging bootstrap and CLI entrypoint.
- `config/` — configuration templates (`settings.example.yaml`) ready to copy into real deployments.
- `tests/` — smoke tests that ensure the package imports and CLI returns successfully.
- `scripts/` — reserved for future automation; contains a placeholder `.gitkeep` file today.
- `docs/` — planning material, data source references, and operational notes.
- `pyproject.toml` — project metadata, dependencies, and pytest configuration.
- `requirements.txt` — pinned dependency mirror for pure `pip` workflows.
- `Makefile` — convenience wrapper for dependency installation (unchanged).

## Daily Workflow
```bash
cd /Users/michaelmerrick/quanticity_capital
source .venv/bin/activate
python -m pip install -e .[dev]
pytest
```
Run `pytest` after meaningful changes; the suite finishes in milliseconds and guards against import
regressions.

## Environment Variables
- `.env.example` captures placeholders for Alpha Vantage, Redis, and IBKR credentials. Copy it to
  `.env` locally and replace the `changeme` values when secrets are issued.
- At minimum set `ALPHAVANTAGE_API_KEY=<your key>` and `REDIS_URL=redis://localhost:6379/0` (or
  equivalent) before running ingestion commands.
- `config/settings.example.yaml` centralises runtime knobs (log level, cache directories, service
  endpoints). Duplicate it to `config/settings.yaml` and customise as modules come online.
- Update this section whenever new variables or config blocks are introduced.

## Tooling Norms
- Stick with `pip` + `venv` until we formalise broader tooling. Introducing `uv`, `poetry`, etc.
  requires an update here.
- Keep dependencies pinned in both `pyproject.toml` and `requirements.txt` to avoid drift.
- Capture recurring operational scripts in `scripts/` once they exist.

## Ongoing Maintenance
- Refresh this guide when the repository layout or bootstrap flow evolves.
- Log troubleshooting notes (install errors, version mismatches) in a new subsection so the next
  developer can pick up quickly.
