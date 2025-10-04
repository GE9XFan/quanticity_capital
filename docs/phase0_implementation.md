# Phase 0 Implementation Guide

## Objective
Lay the groundwork for the automated options trading platform by creating repository scaffolding, environment tooling, and baseline service stubs. This phase focuses on structure, not business logic.

## Deliverables
- Project directory layout with `src/`, `tests/`, `docs/`, and `sql/` folders.
- FastAPI application skeleton with health endpoints and configuration loader.
- Dependency management via pip-tools (`requirements.in` and generated `requirements.txt`).
- Dockerfile and docker-compose stack for app, Redis, and Postgres (Redis kept internal to avoid host port conflicts).
- Makefile targets for common development tasks.
- `.env.example` covering required secrets and connection details; `.gitignore` updated to prevent committing secrets.
- Initial pytest smoke tests for application startup (`make test`).
- Documentation updates: project scope, agents overview, runtime environment matrix, and this guide.

## File Map (Phase 0)
```
.
├── Dockerfile
├── Makefile
├── docker-compose.yml
├── requirements.in
├── requirements.txt
├── .gitignore
├── .env.example
├── docs/
│   ├── project_scope.md
│   ├── agents.md
│   ├── phase0_implementation.md
│   ├── runtime_environment.md
│   └── runtime_versions.txt
├── sql/
│   └── README.md (create during DB scripting)
├── src/
│   └── app/
│       ├── __init__.py
│       ├── api/
│       │   └── router.py
│       ├── config.py
│       └── main.py
└── tests/
    └── test_app.py
```

## Setup Steps
1. **Install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install pip-tools
   make compile
   make install
   ```

2. **Run unit tests**
   ```bash
   make test
   ```

3. **Start services locally (optional)**
   ```bash
   cp .env.example .env
   docker compose up --build
   ```
   Health endpoint available at `http://localhost:8000/health`.
   - If a local Redis already occupies port 6379, the compose stack's Redis service runs without host port exposure.

4. **Update documentation**
   - Reflect any structure changes in `docs/project_scope.md`, `docs/agents.md`, and `docs/runtime_environment.md`.
   - Refresh `docs/runtime_versions.txt` after dependency changes (`pip freeze > docs/runtime_versions.txt`).
   - Log decisions or notes from this phase in this guide.

## Open Items for Future Phases
- Populate `sql/` directory with schema scripts once tables are defined.
- Wire Prometheus exporter and detailed metrics in a later phase.
- Expand tests to cover integration scenarios after ingestion logic is implemented.
- Record completion in scope/agents docs and revisit after each phase (ongoing discipline).
