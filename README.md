# Quanticity Capital

Seed repository for the Quanticity Capital data platform. The current baseline ships a Python package
skeleton, configuration templates, and smoke tests so future phases can build on a working foundation.

## Quick Start
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .[dev]
pytest
```

Verify the CLI entry point once dependencies are installed:
```bash
quanticity-capital --help
quanticity-capital --version
```

## Repository Layout
- `src/quanticity_capital/` — package stub with logging bootstrap and CLI entry point.
- `config/` — configuration templates ready to copy into runtime deployments.
- `tests/` — smoke tests that ensure imports and CLI execution succeed.
- `scripts/` — reserved for automation that will arrive in later phases.
- `docs/` — setup guides, implementation plans, domain references, and samples.
- `pyproject.toml` — project metadata, dependency pins, and pytest defaults.
- `requirements.txt` — pinned mirror for legacy installation workflows.

## Roadmap
Implementation is tracked in `docs/implementation_plan.md`; Phase 2 focuses on Alpha Vantage
ingestion. Refer to the documentation index (`docs/README.md`) for the full knowledge base.

## Contributing
- Keep dependencies pinned in both `pyproject.toml` and `requirements.txt`.
- Run `pytest` before submitting changes.
- Update the documentation in the same commit whenever behaviour or repo layout changes.
