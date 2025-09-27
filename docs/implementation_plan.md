# Implementation Plan (October 2025 Baseline)

The repository now contains a minimal Python package, configuration templates, and smoke tests to
anchor future engineering work. Documentation remains the primary guide for phased delivery.

## Phase 0 – Documentation & Environment (✅ complete)
- Consolidated historical notes into `docs/` so newcomers understand the roadmap.
- Published plain-`pip` bootstrap instructions in `docs/setup.md`.
- Maintained `requirements.txt` with the handful of libraries referenced in the docs.

## Phase 1 – Repository Skeleton (✅ complete)
- Introduced the `src/`, `config/`, `tests/`, and `scripts/` directories using a src-layout package.
- Added `pyproject.toml`, `quanticity_capital/__init__.py`, and `quanticity_capital/main.py` with a
  logging bootstrap and CLI entry point (exposed as `quanticity-capital`).
- Seeded `.env.example` and `config/settings.example.yaml` to standardise runtime configuration.
- Wired pytest defaults in `pyproject.toml` and added `tests/test_imports.py` to ensure the package
  imports and the CLI exits cleanly.

## Phase 2 – Alpha Vantage Ingestion (✅ complete)
- Implemented the full 19-endpoint catalog with NEWS_SENTIMENT constrained to equities and stored
  representative payloads under `docs/samples/`.
- Delivered a shared ingestion runner with retry/backoff, metadata envelopes, and TTL guardrails
  mastered in `config/settings.yaml`.
- Wired runner, scheduler, and orchestrator tiers so CLI runs and scheduled jobs persist payloads to
  Redis while emitting health metrics for tests.
- Updated operational docs (`docs/data_sources.md`, `docs/cli_operations.md`) to mirror the live
  contracts and controls.

## Phase 3 – Interactive Brokers Connectivity (next)
- Implement quotes, level-2 depth, account bundle, and executions using ib_insync.
- Mirror each stream’s Redis contract in `docs/data_sources.md` and note operational runbooks in
  `docs/modules.md`.
- Add integration tests that rely on the paper TWS environment before expanding outward.

## Phase 4 – Analytics Foundations (future)
- Define analytics jobs in `config/analytics.yml` once ingestion payloads are stable.
- Implement workers that consume Redis data and emit `derived:*` keys with freshness metadata.
- Reuse captured fixtures to build “offline” analytics tests so CI stays deterministic.

## Deferred Workstreams
- Signal engine, execution/risk, watchdog, social distribution, dashboards, and cloud deployment stay
  on the shelf until the ingestion + analytics loop is stable.
- Each deferred item should receive its own mini-plan before development begins; link them here when
  specs exist.

## Operating Rhythm
- Keep documentation accurate to the live repository; update this plan as soon as a phase starts or
  finishes.
- Capture open questions in a dedicated `docs/notes.md` (to be added) rather than embedding them in
  code comments.
- Group changes by phase when possible so review context stays clear.
