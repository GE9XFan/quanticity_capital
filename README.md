# Quanticity Capital – Automated Options Trading Platform

This repository houses the solo-development project for the SPY/QQQ/IWM automated options trading stack. Phase 0 is complete, and Phase 1 ingestion is feature-complete but still has follow-up tasks before sign-off:

- **Phase 0** – Repo scaffold, FastAPI app factory, Docker stack, runtime docs ✅
- **Phase 1** – Unusual Whales ingestion worker (WebSocket + REST), Redis live cache, Postgres persistence, raw REST archive ✅ *(metrics exporter + feed classification outstanding)*

## Current Layout

```
src/
  app/            FastAPI service (Phase 0 skeleton, metrics endpoint todo)
  ingestion/      Unusual Whales worker (service, handlers, REST scheduler, rate limit)
sql/              Ad-hoc SQL scripts (`20250104_uw_phase1_tables.sql`)
docs/             Scope, implementation guides, API queries/samples
tests/            Pytest suites + fixture payloads under `tests/data/uw`
```

## Getting Started

```bash
# install dependencies
make install

# run unit tests (uses local venv)
make test

# launch FastAPI (Phase 0 skeleton)
make run

# launch ingestion worker (requires `.env` with UNUSUAL_WHALES_API_TOKEN)
make ingest-run
```

Docker users can run the full stack via `make docker-up` (FastAPI, Postgres, Redis, ingestion worker).

## Documentation

- `docs/project_scope.md` – overall roadmap and guiding principles.
- `docs/phase1_implementation.md` – detailed ingestion design, verified endpoint catalog, outstanding follow-ups.
- `docs/api_queries.md` – REST/WebSocket request examples (token placeholders, sanitized).
- `docs/api_samples/` – JSON snapshots collected from live REST calls.

## Outstanding Follow-ups (Phase 1 sign-off blockers)

- Expose ingestion metrics from the FastAPI service (`/metrics`).
- Classify each REST/WebSocket feed (Redis snapshot vs Postgres archive vs future derived table) prior to building curated tables in Phase 2.
- Keep `docs/api_queries.md` in sync with any new payload observations.

## Environment & Secrets

Create a `.env` (gitignored) with `UNUSUAL_WHALES_API_TOKEN` and database/redis connection strings as needed. See `src/app/config.py` and `src/ingestion/config.py` for the full list of tunable settings.

---

Questions? Open an issue or ping the project notes—future phases will build analytics, risk, execution, and distribution on top of this ingestion foundation.
