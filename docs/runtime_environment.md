# Runtime Environment & Version Matrix

This document captures the exact toolchain and dependency versions in use for the automated options trading platform. Keep it synchronized with the active development environment so troubleshooting and onboarding remain painless.

## 1. Host Prerequisites
These versions reflect the local macOS development machine as of Phase 0 completion.

| Component | Version | Notes |
|-----------|---------|-------|
| Python (venv) | 3.11.13 | Created via `python3.11 -m venv venv`; primary interpreter for all services. |
| pip | 25.2 | Reported by `python -m pip --version` inside the virtualenv. |
| pip-tools | 7.5.1 | Installed alongside requirements to provide `pip-compile`. |
| PostgreSQL CLI (`psql`) | 16.10 (Homebrew) | Local client; containerized Postgres currently uses 15.x (see §2). |
| Redis server (host) | 8.2.1 | Homebrew install; local instance left running while Docker uses an internal Redis. |
| Docker Engine | (Docker Desktop for Mac) | Version managed outside this repo—ensure it’s current enough to run Compose v2. |

> When upgrading any prerequisite, record the change here and validate that dependent services (Docker images, Python packages) remain compatible.

## 2. Containerized Services (docker-compose)
The development stack relies on the following images and versions:

- `python:3.11-slim` – base image for the FastAPI application (`Dockerfile`).
- `redis:7-alpine` – in-stack Redis instance with append-only persistence (`docker-compose.yml`).
- `postgres:15` – Postgres server for development/testing; credentials sourced from `.env`.

If you need to align the container versions with newer host versions (e.g., upgrade to Postgres 16), update the image tags in `docker-compose.yml` and document the change here.

## 3. Python Dependency Snapshot
A full `pip freeze` taken from the active virtual environment lives in `docs/runtime_versions.txt`. Regenerate whenever `requirements.in` changes:

```bash
source venv/bin/activate
pip-compile requirements.in --output-file requirements.txt
pip install -r requirements.txt
pip freeze > docs/runtime_versions.txt
```

Key libraries at Phase 0:

- FastAPI 0.118.0
- Uvicorn 0.37.0 (with `standard` extras: httptools 0.6.4, uvloop 0.21.0, websockets 15.0.1, watchfiles 1.1.0)
- Redis client 6.4.0
- Psycopg 3.2.10 (binary bindings enabled)
- HTTPX 0.28.1
- Pydantic 2.11.9 + Pydantic Settings 2.11.0
- python-dotenv 1.1.1
- pytest 8.4.2 for smoke tests

Refer to the freeze file for the complete list.

## 4. Environment Files & Version Control
- `.env.example` documents required secrets and connection details; copy to `.env` for local use. `.gitignore` blocks both `.env` and the virtualenv directory to prevent leakage.
- When rotating secrets or IDs (e.g., `IB_CLIENT_ID`, API tokens), update `.env.example` placeholders but never commit real values.

## 5. Maintenance Checklist
- **After dependencies change:** run the freeze steps above, update this document with any notable version bumps, and notify collaborators.
- **Before onboarding a new machine:** replicate the versions listed here to avoid subtle runtime differences.
- **During CI/CD setup:** use these versions as the baseline (Python 3.11, Postgres 15+, Redis 7+) unless there is an explicit decision to upgrade.

Keeping this matrix current saves us from guesswork when a bug only reproduces under a specific interpreter or database release.
